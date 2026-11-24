"""Async client for LG soundbars controlled over Bluetooth serial (SPP)."""

from __future__ import annotations

import asyncio
import contextlib
import errno
import logging
import time
from asyncio import FIRST_COMPLETED
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from bluetooth_classic import (
    SERIAL_PORT,
    RfcommUnsupportedError,
    Security,
    normalize_address,
    open_rfcomm,
)

from .const import (
    COMBINED_ARC_FUNCTIONS,
    CONNECT_STATE_COMMANDS,
    DEFAULT_VOLUME_MAX,
    FIRMWARE_INFO_ALL,
    LEVEL_COMMANDS,
    SETTING_FEATURES,
    SUPPORTED_CHIP_TYPES,
    SWITCH_COMMANDS,
    Category,
    EqCommand,
    Feature,
    Function,
    FunctionCommand,
    GeneralCommand,
    UpdateCommand,
    UtilityCommand,
)
from .exceptions import (
    BluetoothUnsupported,
    CannotConnect,
    HandshakeFailed,
    NotConnected,
)
from .protocol import Frame, FrameParser
from .state import SoundbarState

_LOGGER = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT = 15.0
HANDSHAKE_TIMEOUT = 5.0
# After the initial queries, wait until the soundbar has been quiet this long
# (bounded by SETTLE_MAX) so callers see every feature it answered for.
SETTLE_QUIET = 1.0
SETTLE_MAX = 6.0
SEND_INTERVAL = 0.05
# As the LG app does for each start-up step: wait this long for the answer,
# asking up to ASK_ATTEMPTS times. Unlike the app, carry on without it.
ASK_TIMEOUT = 3.0
# How long to wait for the soundbar to reach the input switched back to, and
# how many more times to select it if it does not.
SWITCH_WAIT = 3.0
SWITCH_ATTEMPTS = 2
ASK_ATTEMPTS = 3
# As the LG app does, wait this long for a soundbar with an MTK chip that
# says it is still starting up, and run the start-up again once it is done.
MTK_BOOT_TIMEOUT = 20.0
# How many times the start-up runs again for that before giving up.
MTK_BOOT_RESTARTS = 2
# Values of MTK_BOOT_STATE.
MTK_BOOT_STARTED = 0x00
MTK_BOOT_COMPLETED = 0x01
CLOSE_TIMEOUT = 2.0
# Linux reports EBUSY for a moment after an RFCOMM link to the same channel
# closes, for example when setup's test connection has just ended.
BUSY_RETRIES = 3
BUSY_DELAY = 1.0


class Connector(Protocol):
    """Opens a connection and attaches the protocol to it."""

    def __call__(
        self,
        address: str,
        channel: int | None,
        protocol_factory: Callable[[], asyncio.Protocol],
        timeout: float,
        *,
        write_on_connect: bytes,
    ) -> Awaitable[tuple[asyncio.Transport, asyncio.Protocol]]:
        """Open the soundbar's serial port, writing write_on_connect at once.

        ``channel`` is the RFCOMM channel to try first, if known. The
        transport's ``get_extra_info("rfcomm_channel")`` is the channel used.
        """


async def _open_link(
    address: str,
    channel: int | None,
    protocol_factory: Callable[[], asyncio.Protocol],
    timeout: float,
    *,
    write_on_connect: bytes,
) -> tuple[asyncio.Transport, asyncio.Protocol]:
    """Open the soundbar's Serial Port service with an encrypted link.

    The channel given is tried first; without one, or if the soundbar refuses
    it, the service's channel is looked up in its SDP records. Android
    encrypts the link to a paired device. Whether soundbars need it is
    untested.
    """
    try:
        return await open_rfcomm(
            address,
            protocol_factory,
            service=SERIAL_PORT,
            channel=channel,
            timeout=timeout,
            write_on_connect=write_on_connect,
            security=Security.MEDIUM,
        )
    except RfcommUnsupportedError as err:
        raise BluetoothUnsupported(str(err)) from err


class _SoundbarProtocol(asyncio.Protocol):
    """Feeds received bytes to the client as frames."""

    def __init__(self, client: LGSoundbar) -> None:
        self._client = client
        self._parser = FrameParser()
        self.closed = asyncio.Event()

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        # Before any data is handled: replies to the request the connector
        # sent may already be waiting.
        self._client._attach(self, transport)

    def data_received(self, data: bytes) -> None:
        for frame in self._parser.feed(data):
            self._client._handle_frame(frame)

    def connection_lost(self, exc: Exception | None) -> None:
        self.closed.set()
        self._client._handle_connection_lost(self, exc)


@dataclass(frozen=True, slots=True)
class InputRestore:
    """How putting back the input a connection moved the soundbar from went."""

    #: The input the soundbar reported first, before any move; None if it
    #: moved before answering.
    reported: int | None
    #: Whether the connection moved it to Bluetooth.
    moved: bool
    #: The code sent to switch back as the move was seen, if any.
    sent: int | None
    #: Whether it ended up on the input it reported.
    reached: bool
    #: How many more times the input was selected after the first switch.
    attempts: int


class LGSoundbar:
    """An LG soundbar reached over Bluetooth Classic RFCOMM."""

    def __init__(
        self,
        address: str,
        channel: int | None = None,
        *,
        connector: Connector = _open_link,
        send_interval: float = SEND_INTERVAL,
        settle_quiet: float = SETTLE_QUIET,
        settle_max: float = SETTLE_MAX,
        ask_timeout: float = ASK_TIMEOUT,
        switch_wait: float = SWITCH_WAIT,
        known_features: Iterable[int] | None = None,
    ) -> None:
        """Create a client; call connect() to open the connection."""
        self.address = normalize_address(address)
        # The RFCOMM channel of the last connection, tried first next time.
        self.channel = channel
        self.state = SoundbarState()
        self._connector = connector
        self._send_interval = send_interval
        self._settle_quiet = settle_quiet
        self._settle_max = settle_max
        self._ask_timeout = ask_timeout
        self._switch_wait = switch_wait
        # How the last connect(keep_input=True) put the input back.
        self.input_restore: InputRestore | None = None
        # Extended feature flags from an earlier connection. Until this
        # connection's arrive, they decide how to switch back to Optical, ARC
        # or eARC, so that need not wait for them. Not shown in the state.
        self.known_features: frozenset[int] | None = (
            frozenset(known_features) if known_features is not None else None
        )
        # The start-up step waiting for its answer, and the future to set.
        self._waiting_for: tuple[Frame, asyncio.Future[None]] | None = None
        # One connect() at a time: a second call waits for the first.
        self._connect_lock = asyncio.Lock()
        self._transport: asyncio.Transport | None = None
        self._protocol: _SoundbarProtocol | None = None
        self._callbacks: list[Callable[[], None]] = []
        self._function_known = asyncio.Event()
        self._last_frame = 0.0
        self._ready = False
        self._answered = False
        self._closed_in_handshake = False
        self._close_reason: Exception | None = None
        self._initial_function: int | None = None
        # Whether to switch straight back if the connection moves the
        # soundbar to Bluetooth.
        self._keep_input = False
        # Set once the soundbar has moved to Bluetooth, until switched back.
        self._moved_from: int | None = None
        self._restored_input: int | None = None
        self._ready_at: float | None = None
        self._last_duration: float | None = None
        # When the connection opened, and seconds from then to each step.
        self._opened_at: float | None = None
        self._timings: dict[str, float] = {}
        # Bluetooth reports of the current input before the handshake ends.
        self._bluetooth_reports = 0
        self._moved_before_answering = False
        # Set once a start-up step has gone unanswered.
        self._step_unanswered = False
        # Set when the soundbar reports its MTK start-up state while
        # connecting: started (still starting up) or completed.
        self._boot_reported = asyncio.Event()
        self._boot_completed = asyncio.Event()
        # Whether the soundbar has reached the input switched back to, and
        # whether it has been selected again after leaving it.
        self._switch_back_reached = False
        self._switched_back_again = False

    @property
    def connected(self) -> bool:
        """Return whether the connection is open and initialised."""
        return self._transport is not None and self._ready

    @property
    def initial_function(self) -> int | None:
        """Return the input the soundbar first reported on this connection.

        A soundbar that is on switches to Bluetooth as a control connection
        opens, but first reports the input it was on; one woken by the
        connection reports Bluetooth from the start.
        """
        return self._initial_function

    @property
    def restored_input(self) -> int | None:
        """Return the code sent to switch back during the last handshake."""
        return self._restored_input

    @property
    def timings(self) -> dict[str, float]:
        """Return seconds from the connection opening to each handshake step.

        "connecting" is how long until Home Assistant took over the opened
        connection, and the steps are measured from then. The current input
        was asked for as the connection opened, which may be earlier when
        Home Assistant is busy. Steps: "first input" (the first input
        reported),
        "moved" (to Bluetooth by the connection), "moved before answering"
        (see moved_before_answering), "flags" (the extended feature flags),
        "switched back" (the input selected again), "switched back again"
        (after the soundbar left it) and "ready". A step that
        did not happen is left out.
        """
        return dict(self._timings)

    @property
    def moved_before_answering(self) -> bool:
        """Return whether the soundbar seemed to move before answering.

        A soundbar that moves to Bluetooth before answering reports
        Bluetooth twice: its own report of the move, then its answer. The
        input it was on is then not known. (Seen on an LG G1; that one on
        Bluetooth throughout reports it only once is unconfirmed.)
        """
        return self._moved_before_answering

    @property
    def last_duration(self) -> float | None:
        """Return how many seconds the last connection lasted once set up."""
        return self._last_duration

    @property
    def close_reason(self) -> Exception | None:
        """Return why the last connection closed, if it closed with an error."""
        return self._close_reason

    def register_callback(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Call callback on each state change or disconnect; return an unsubscriber."""
        self._callbacks.append(callback)

        def remove() -> None:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return remove

    async def connect(
        self,
        timeout: float = DEFAULT_CONNECT_TIMEOUT,
        *,
        keep_input: bool = False,
    ) -> None:
        """Open the connection, run the handshake and read the initial state.

        A soundbar that is on moves to Bluetooth as the connection opens,
        after first reporting the input it was on. With keep_input, that
        input is selected again as soon as the move is seen: straight away
        with the code it reported, or for Optical, ARC and eARC once the
        feature flags tell whether they are one input (selected as
        Optical/HDMI ARC, as the LG app does; a G1 ignores its eARC code).
        connect() then waits until the soundbar is on that input, selects it
        again if it is not, and records how it went in input_restore.

        The channel of the last connection is tried first; without one, or
        if the soundbar refuses it, the connector looks up its Serial Port
        service. If that channel accepts the connection but nothing on it
        answers (another service now on it), the service is looked up once
        more; a soundbar that answered or closed the link is not connected to
        again. A looked-up channel is kept even if the handshake fails.
        """
        async with self._connect_lock:
            if self._transport is not None:
                return
            self.input_restore = None
            await self._open(timeout, keep_input)
            if keep_input:
                self.input_restore = await self._restore_input()

    async def _open(self, timeout: float, keep_input: bool) -> None:
        self._keep_input = keep_input
        hint = self.channel
        try:
            await self._connect_once(hint, timeout)
        except HandshakeFailed:
            # Only a channel that accepted the connection but sent nothing,
            # not even the input, may now be another service. A soundbar
            # that answered (and may have moved to Bluetooth) or closed the
            # link (switching off, not trusted) is not connected to again.
            if hint is None or self._answered or self._closed_in_handshake:
                raise
            _LOGGER.debug(
                "Nothing answered on RFCOMM channel %s of %s; looking it up",
                hint,
                self.address,
            )
            # The channel the lookup finds replaces the hint, even if this
            # attempt fails too; a failure before then keeps the hint.
            await self._connect_once(None, timeout)

    async def _connect_once(self, channel: int | None, timeout: float) -> None:
        try:
            await self._connect_channel_when_free(channel, timeout)
        except CannotConnect:
            raise
        except (OSError, TimeoutError) as err:
            # Unreachable, refused, or the service could not be looked up.
            raise CannotConnect(
                f"Could not connect to {self.address}: {err!r}"
            ) from err

    async def disconnect(self) -> None:
        """Close the connection and wait until the socket is closed."""
        protocol = self._protocol
        if self._transport is not None:
            self._transport.close()
        if protocol is not None:
            try:
                async with asyncio.timeout(CLOSE_TIMEOUT):
                    await protocol.closed.wait()
            except TimeoutError:
                _LOGGER.debug("Connection to %s did not close in time", self.address)

    async def refresh(self, *, flags: bool = True) -> None:
        """Ask the soundbar to report its whole state again.

        Without flags, the feature flags are not asked for again, as when the
        handshake has just asked for them.
        """
        function = self._require_function()
        frames = [
            Frame(function, FunctionCommand.CURR_FEATURE_STATE),
            Frame(Category.GENERAL, GeneralCommand.SUPPORTED_MODE),
            Frame(Category.GENERAL, GeneralCommand.SUPPORTED_FEATURE_LISTS),
            *(
                [
                    Frame(
                        Category.GENERAL,
                        GeneralCommand.EXTENDED_SUPPORTED_FEATURE_LISTS,
                    )
                ]
                if flags
                else []
            ),
            Frame(Category.GENERAL, GeneralCommand.MODEL_TYPE_INFO),
            *self._input_queries(function),
            *self._setting_queries(function),
        ]
        await self._send_many(frames)

    def _flagged(self, feature: Feature) -> bool:
        """Return whether to ask for something its flag gates.

        As the LG app does, once the extended feature flags are known; until
        then (a soundbar that has none, or did not send them), everything is
        asked for.
        """
        return self.state.features is None or feature in self.state.features

    def _setting_queries(self, function: int) -> list[Frame]:
        """Return the queries the LG app sends once it has the feature flags."""
        flags = self.state.features
        frames = [Frame(function, minor) for minor in self._input_state_minors()]
        frames.extend(
            Frame(Category.UTILITY, command)
            for command in sorted(LEVEL_COMMANDS | SWITCH_COMMANDS)
            if self._flagged(SETTING_FEATURES[command])
        )
        if self._flagged(Feature.SPECIAL_EQ):
            frames.append(Frame(Category.UTILITY, UtilityCommand.SPECIAL_EQ))
        if flags is not None and Feature.MODEL_TYPE_NEW in flags:
            frames.append(Frame(Category.GENERAL, GeneralCommand.MODEL_TYPE_INFO_NEW))
        if flags is None:
            # The LG app never asks for the sleep timer; it offers it when the
            # feature list says so and reads the soundbar's own reports. Kept
            # for soundbars without feature flags, as before.
            frames.append(Frame(Category.UTILITY, UtilityCommand.SLEEP_TIMER_SETTING))
        if self.state.asks_woofer_state:
            frames.append(Frame(Category.UTILITY, UtilityCommand.WOOFER_STATE))
        if self.state.asks_rear_state:
            frames.append(Frame(Category.UTILITY, UtilityCommand.REAR_STATE))
        if self.state.firmware_info_available is not False:
            # Read-only: the chips and their versions. Newer soundbars are
            # asked with FIRMWARE_TYPE_NEW, as by the app.
            frames.append(
                Frame(
                    Category.UPDATE,
                    UpdateCommand.FIRMWARE_TYPE_NEW
                    if flags is not None and Feature.FIRMWARE_INFO_NEW in flags
                    else UpdateCommand.FIRMWARE_TYPE,
                )
            )
        return frames

    def _input_state_minors(self) -> list[int]:
        """Return the night mode and audio format queries their flags allow."""
        minors: list[int] = []
        if self._flagged(Feature.NIGHT_MODE):
            minors.append(FunctionCommand.NIGHT_MODE)
        if self._flagged(Feature.AUDIO_INFO):
            minors.append(FunctionCommand.AUDIO_INFO)
        return minors

    @staticmethod
    def _input_queries(function: int) -> list[Frame]:
        """Return queries for the input's connection states."""
        return [
            Frame(function, minor) for minor in CONNECT_STATE_COMMANDS.get(function, ())
        ]

    async def select_function(self, function: int) -> None:
        """Switch to an input function."""
        await self._send(
            Frame(Category.GENERAL, GeneralCommand.SET_MODE, bytes((function,)))
        )

    async def set_volume(self, volume: int) -> None:
        """Set the volume, from 0 to the soundbar's maximum."""
        function = self._require_function()
        maximum = self.state.volume_max or DEFAULT_VOLUME_MAX
        volume = max(0, min(maximum, volume))
        await self._send(
            Frame(function, FunctionCommand.VOLUME_CONTROL, bytes((maximum, volume)))
        )

    async def set_mute(self, mute: bool) -> None:
        """Mute or unmute."""
        function = self._require_function()
        await self._send(Frame(function, FunctionCommand.MUTE, bytes((int(mute),))))

    async def set_sound_mode(self, sound_mode: int) -> None:
        """Select a sound mode (EQ)."""
        function = self._require_function()
        await self._send(
            Frame(
                function,
                FunctionCommand.EQ,
                bytes((EqCommand.CURRENT_EQ_INDEX, sound_mode)),
            )
        )

    async def set_night_mode(self, enabled: bool) -> None:
        """Turn night mode on or off."""
        function = self._require_function()
        await self._send(
            Frame(function, FunctionCommand.NIGHT_MODE, bytes((int(enabled),)))
        )

    async def set_level(self, command: UtilityCommand, value: int) -> None:
        """Set a level setting such as woofer, rear or centre level."""
        if command not in LEVEL_COMMANDS:
            raise ValueError(f"{command!r} is not a level setting")
        await self._send(Frame(Category.UTILITY, command, bytes((value & 0xFF,))))

    async def set_switch(self, command: UtilityCommand, enabled: bool) -> None:
        """Turn an on/off setting such as DRC or auto volume on or off."""
        if command not in SWITCH_COMMANDS:
            raise ValueError(f"{command!r} is not an on/off setting")
        await self._send(Frame(Category.UTILITY, command, bytes((int(enabled),))))

    async def set_tone(self, bass: int, treble: int, middle: int = 0) -> None:
        """Set the tone bands, in the soundbar's tone control steps.

        A soundbar that reported three bands takes all three; one that
        reported two takes bass and treble, as in the LG app.
        """
        function = self._require_function()
        if self.state.three_band:
            payload = bytes(
                (
                    EqCommand.USER_EQ_VALUE_3BAND,
                    bass & 0xFF,
                    middle & 0xFF,
                    treble & 0xFF,
                )
            )
        else:
            payload = bytes((EqCommand.USER_EQ_VALUE_2BAND, bass & 0xFF, treble & 0xFF))
        await self._send(Frame(function, FunctionCommand.EQ, payload))

    async def set_sleep_timer(self, minutes: int) -> None:
        """Turn the soundbar off after this many minutes; 0 cancels the timer."""
        if not 0 <= minutes <= 0xFF:
            raise ValueError("minutes must be between 0 and 255")
        await self._send(
            Frame(
                Category.UTILITY,
                UtilityCommand.SLEEP_TIMER_SETTING,
                bytes((int(minutes > 0), minutes)),
            )
        )

    async def power_off(self) -> None:
        """Turn the soundbar off; it closes the connection as it does."""
        await self._send(
            Frame(Category.GENERAL, GeneralCommand.POWER_CONTROL, bytes((0,)))
        )

    async def _connect_channel_when_free(
        self, channel: int | None, timeout: float
    ) -> None:
        # Without a channel, each attempt looks the service up again: a
        # connection that fails as busy does not say which channel it found.
        for attempt in range(BUSY_RETRIES + 1):
            try:
                await self._connect_channel(channel, timeout)
            except OSError as err:
                if err.errno != errno.EBUSY or attempt == BUSY_RETRIES:
                    raise
                _LOGGER.debug("RFCOMM channel %s is still busy; retrying", channel)
                await asyncio.sleep(BUSY_DELAY)
            else:
                return

    async def _connect_channel(self, channel: int | None, timeout: float) -> None:
        _LOGGER.debug(
            "Connecting to %s on RFCOMM channel %s",
            self.address,
            "looked up" if channel is None else channel,
        )
        self._ready = False
        # Whether the soundbar sent anything, and whether it closed the link,
        # during this connection's handshake.
        self._answered = False
        self._closed_in_handshake = False
        self._function_known.clear()
        self._initial_function = None
        self._restored_input = None
        self._moved_from = None
        self._timings = {}
        self._opened_at = None
        self._bluetooth_reports = 0
        self._moved_before_answering = False
        # Set once a start-up step has gone unanswered.
        self._step_unanswered = False
        # Set when the soundbar reports its MTK start-up state while
        # connecting: started (still starting up) or completed.
        self._boot_reported = asyncio.Event()
        self._boot_completed = asyncio.Event()
        # Whether the soundbar has reached the input switched back to, and
        # whether it has been selected again after leaving it.
        self._switch_back_reached = False
        self._switched_back_again = False
        self.state = SoundbarState()
        started = time.monotonic()
        # The connector writes it the moment the connection opens, so a busy
        # event loop cannot delay it.
        opening_request = Frame(Category.GENERAL, GeneralCommand.MODE)
        transport, protocol = await self._connector(
            self.address,
            channel,
            lambda: _SoundbarProtocol(self),
            timeout,
            write_on_connect=opening_request.encode(),
        )
        opened_at = self._opened_at
        if opened_at is None:
            # A connector whose protocol was not told the connection opened.
            opened_at = self._attach(protocol, transport)  # type: ignore[arg-type]
        self._timings["connecting"] = round(opened_at - started, 3)
        used = transport.get_extra_info("rfcomm_channel")
        _LOGGER.debug(
            "Opened RFCOMM channel %s of %s (%s)",
            used,
            self.address,
            "hint" if channel is not None and used == channel else "looked up",
        )
        if channel is None and isinstance(used, int):
            # Kept even if the handshake fails, so the next attempt need not
            # look it up again.
            self.channel = used
        _LOGGER.debug("Sent %s as the connection opened", opening_request)
        try:
            await self._handshake()
        except NotConnected as err:
            self._closed_in_handshake = True
            self._drop_transport()
            raise HandshakeFailed(
                f"{self.address} closed the connection during the handshake"
                f" ({self._close_reason!r})"
            ) from err
        except BaseException:
            self._drop_transport()
            raise
        self._ready = True
        # Kept to try first next time; a connector that does not say keeps
        # the channel it was given.
        if isinstance(used, int):
            self.channel = used
        elif channel is not None:
            self.channel = channel
        if self.state.features is not None:
            self.known_features = self.state.features
        self._ready_at = time.monotonic()
        self._mark("ready")
        _LOGGER.debug(
            "Connected to %s: %s; timings %s", self.address, self.state, self._timings
        )
        self._notify()

    async def _handshake(self) -> None:
        """Run the LG app's start-up sequence, asking for the input first.

        A soundbar that is on moves to Bluetooth as a connection opens and
        only reports the input it was on if asked before then. So the current
        input is asked for first and alone, by the connector as the connection
        opens, and nothing else is sent until it is reported.

        Then the app's sequence: its opening messages (which the app sends
        before asking for the input), then each step after the answer to the
        one before, as the app does: current state, supported inputs, the
        feature list, then the extended feature flags if the feature list
        says the soundbar has them, then the settings.
        """
        if self._transport is None:
            # Closed (reset) before Home Assistant took over the connection.
            raise NotConnected(f"{self.address} closed the connection")
        again = False
        for _ in range(MTK_BOOT_RESTARTS + 1):
            # A start-up state reported as the connection opened counts.
            start_up = asyncio.ensure_future(self._start_up(again=again))
            boot = asyncio.ensure_future(self._boot_reported.wait())
            try:
                await asyncio.wait({start_up, boot}, return_when=FIRST_COMPLETED)
            finally:
                boot.cancel()
                if not start_up.done():
                    start_up.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await start_up
            if not start_up.cancelled():
                start_up.result()
                return
            if not self._boot_completed.is_set():
                # Still starting up: wait for it to finish, as the app does.
                _LOGGER.debug("%s is still starting up; waiting", self.address)
                try:
                    async with asyncio.timeout(MTK_BOOT_TIMEOUT):
                        await self._boot_completed.wait()
                except TimeoutError as err:
                    raise HandshakeFailed(
                        f"{self.address} did not finish starting up"
                    ) from err
            # Started up: run the start-up again from the beginning.
            _LOGGER.debug("%s has started up; starting again", self.address)
            self._boot_reported.clear()
            self._boot_completed.clear()
            again = True
        raise HandshakeFailed(f"{self.address} kept restarting its start-up")

    async def _start_up(self, *, again: bool) -> None:
        """Run the start-up sequence once; see _handshake.

        When run again, after the soundbar reports it has started up, it asks
        for the current input again first.
        """
        if again:
            self._function_known.clear()
            self._initial_function = None
            await self._send(Frame(Category.GENERAL, GeneralCommand.MODE))
        try:
            async with asyncio.timeout(HANDSHAKE_TIMEOUT):
                await self._function_known.wait()
        except TimeoutError as err:
            raise HandshakeFailed(
                f"{self.address} did not report its current input"
            ) from err
        function = self.state.function
        await self._send_many(
            [
                Frame(Category.GENERAL, GeneralCommand.ANDROID_CHECK_COMMAND),
                Frame(Category.GENERAL, GeneralCommand.EMERGENCY_CHECK_COMMAND),
                Frame(
                    Category.GENERAL,
                    GeneralCommand.SUPPORTED_FIRMWARE_CHIP_TYPE,
                    bytes((SUPPORTED_CHIP_TYPES,)),
                ),
            ]
        )
        await self._ask(
            lambda: Frame(self._require_function(), FunctionCommand.CURR_FEATURE_STATE),
            Frame(Category.GENERAL, GeneralCommand.MODEL_TYPE_INFO),
        )
        if await self._stopped_for_emergency():
            return
        await self._ask(lambda: Frame(Category.GENERAL, GeneralCommand.SUPPORTED_MODE))
        if await self._stopped_for_emergency():
            return
        await self._send_many(self._input_queries(self._require_function()))
        await self._ask(
            lambda: Frame(Category.GENERAL, GeneralCommand.SUPPORTED_FEATURE_LISTS)
        )
        if await self._stopped_for_emergency():
            return
        if self.state.extended_flags_available is not False:
            # Also asked when the feature list did not come, as before.
            await self._ask(
                lambda: Frame(
                    Category.GENERAL, GeneralCommand.EXTENDED_SUPPORTED_FEATURE_LISTS
                )
            )
        if self.state.features is not None and (
            Feature.EXTENDED_FEATURES_2 in self.state.features
        ):
            await self._ask(
                lambda: Frame(
                    Category.GENERAL, GeneralCommand.EXTENDED_SUPPORTED_FEATURE_2_LISTS
                )
            )
        await self._send_many(self._setting_queries(self._require_function()))
        await self._wait_until_quiet()
        if self._moved_from is not None:
            # Still waiting for feature flags that never came: a soundbar
            # without them takes its inputs' own codes.
            self._switch_back(self._moved_from)
            await self._wait_until_quiet()
        if self.state.function not in (None, function):
            # The input changed during the handshake, as when switching back
            # from Bluetooth: read the new input's volume and modes.
            current = self._require_function()
            await self._send_many(
                [
                    Frame(current, FunctionCommand.CURR_FEATURE_STATE),
                    *(Frame(current, m) for m in self._input_state_minors()),
                    *self._input_queries(current),
                ]
            )
            await self._wait_until_quiet()
        if self._transport is None:
            raise HandshakeFailed(
                f"{self.address} closed the connection while reporting its state"
                f" ({self._close_reason!r})"
            )

    async def _stopped_for_emergency(self) -> bool:
        """Stop the start-up if the soundbar is in emergency mode.

        A soundbar left so by a failed firmware update answers the emergency
        check with 01. The LG app then stops its start-up, asks for the
        firmware chips and offers its recovery update; this does the same,
        short of the update. Unconfirmed on a real soundbar.
        """
        if not self.state.emergency:
            return False
        _LOGGER.warning(
            "%s is in emergency mode after a failed firmware update; LG's app"
            " can recover it",
            self.address,
        )
        self._mark("emergency")
        await self._send(Frame(Category.UPDATE, UpdateCommand.FIRMWARE_TYPE))
        await self._wait_until_quiet()
        return True

    async def _ask(self, frame: Callable[[], Frame], *also: Frame) -> bool:
        """Send a start-up step and wait for its answer, as the LG app does.

        The app asks again every 3 seconds, 3 times in all, then gives up on
        the connection; this carries on without the answer instead. frame is
        built for each attempt (the current input may change); the frames in
        also go with the first attempt without waiting for theirs.
        """
        loop = asyncio.get_running_loop()
        # Once a step has gone unanswered, the soundbar probably does not
        # speak that part of the protocol: ask later steps only once.
        for attempt in range(1 if self._step_unanswered else ASK_ATTEMPTS):
            question = frame()
            answered: asyncio.Future[None] = loop.create_future()
            self._waiting_for = (question, answered)
            try:
                await self._send(question)
                if not attempt:
                    await self._send_many(also)
                async with asyncio.timeout(self._ask_timeout):
                    await answered
            except TimeoutError:
                continue
            finally:
                self._waiting_for = None
            return True
        _LOGGER.debug("%s did not answer %s", self.address, frame())
        self._step_unanswered = True
        return False

    def _answer_waiting(self, frame: Frame) -> None:
        """Wake the start-up step this frame answers, if any."""
        if self._waiting_for is None:
            return
        question, answered = self._waiting_for
        general = (Category.GENERAL, Category.UTILITY, Category.UPDATE)
        if frame.minor != question.minor or answered.done():
            return
        if frame.major == question.major or (
            # An input's answer comes from the input the soundbar is on now.
            question.major not in general and frame.major not in general
        ):
            answered.set_result(None)

    async def _wait_until_quiet(self) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._settle_max
        while (now := loop.time()) < deadline:
            quiet_until = self._last_frame + self._settle_quiet
            if now >= quiet_until:
                return
            await asyncio.sleep(min(quiet_until, deadline) - now)

    def _require_function(self) -> int:
        if self._transport is None:
            raise NotConnected(f"{self.address} is not connected")
        if (function := self.state.function) is None:
            raise NotConnected(f"{self.address} has not reported its input")
        return function

    async def _send(self, frame: Frame) -> None:
        if self._transport is None:
            raise NotConnected(f"{self.address} is not connected")
        self._write(frame)

    async def _send_many(self, frames: Iterable[Frame]) -> None:
        for index, frame in enumerate(frames):
            if index:
                await asyncio.sleep(self._send_interval)
            await self._send(frame)

    def _write(self, frame: Frame) -> None:
        if self._transport is None:
            return
        _LOGGER.debug("Sending %s", frame)
        self._transport.write(frame.encode())

    def _handle_frame(self, frame: Frame) -> None:
        self._answered = True
        self._last_frame = asyncio.get_running_loop().time()
        _LOGGER.debug("Received %s", frame)
        self._answer_waiting(frame)
        if (
            frame.major == Category.GENERAL
            and frame.minor == GeneralCommand.MTK_BOOT_STATE
            and frame.payload
            and not self._ready
        ):
            self._note_boot_state(frame.payload[0])
        if frame.major == Category.GENERAL and frame.minor == GeneralCommand.WATCH_DOG:
            # The app answers the soundbar's watchdog to keep the session alive.
            self._write(Frame(Category.GENERAL, GeneralCommand.WATCH_DOG))
        previous_function = self.state.function
        previous_chips = list(self.state.firmware_chips)
        flags_known = self.state.features is not None
        changed = self.state.apply(frame)
        if not flags_known and self.state.features is not None:
            self._mark("flags")
        if self.state.firmware_chips != previous_chips:
            # Ask each chip for its details, as the LG app does.
            for chip in self.state.firmware_chips:
                self._write(
                    Frame(
                        Category.UPDATE,
                        UpdateCommand.FIRMWARE_INFO,
                        bytes((chip, FIRMWARE_INFO_ALL)),
                    )
                )
        function = self.state.function
        if function is None:
            return
        if (
            not self._ready
            and frame.major == Category.GENERAL
            and frame.minor == GeneralCommand.MODE
            and function == Function.BLUETOOTH
            and self._initial_function in (None, Function.BLUETOOTH)
        ):
            self._bluetooth_reports += 1
            if self._bluetooth_reports == 2:
                _LOGGER.debug(
                    "%s reported Bluetooth twice; it moved before answering",
                    self.address,
                )
                self._moved_before_answering = True
                self._mark("moved before answering")
        if self._initial_function is None:
            self._initial_function = function
            self._mark("first input")
        elif (
            not self._ready
            and self._keep_input
            and self._moved_from is None
            and self._restored_input is None
            and function == Function.BLUETOOTH
            and previous_function != Function.BLUETOOTH
            and self._initial_function != Function.BLUETOOTH
        ):
            # Moved to Bluetooth by the connection: switch straight back,
            # waiting for the feature flags if they decide the code.
            _LOGGER.debug(
                "%s moved to Bluetooth as the connection opened", self.address
            )
            self._moved_from = self._initial_function
            self._mark("moved")
        self._maybe_switch_back()
        self._keep_switched_back(function)
        self._function_known.set()
        if self._ready and function != previous_function:
            # The input changed; ask for the new input's volume and modes.
            self._write(Frame(function, FunctionCommand.CURR_FEATURE_STATE))
            for minor in self._input_state_minors():
                self._write(Frame(function, minor))
            for frame in self._input_queries(function):
                self._write(frame)
        if changed and self._ready:
            self._notify()

    def _maybe_switch_back(self) -> None:
        """Switch back; for Optical, ARC and eARC once the flags are known."""
        function = self._moved_from
        if function is None or self._transport is None:
            return
        if (code := self._switch_back_code(function)) is not None:
            self._switch_back(code)

    def _switch_back_code(self, function: int) -> int | None:
        """Return the code that selects an input, or None until it is known.

        Optical, ARC and eARC are selected as Optical/HDMI ARC when the
        feature flags say they are one input, which takes the flags of this
        connection or, until they arrive, of an earlier one.
        """
        if function not in COMBINED_ARC_FUNCTIONS:
            return function
        flags = self.state.features
        if flags is None and (flags := self.known_features) is not None:
            _LOGGER.debug(
                "%s: switching back with the feature flags of an earlier connection",
                self.address,
            )
        if flags is None:
            return None
        return (
            Function.OPT_HDMI_ARC if Feature.OPT_HDMI_ARC_SUPPORT in flags else function
        )

    @staticmethod
    def _same_input(function: int | None, code: int) -> bool:
        """Return whether the soundbar is on the input a code selects."""
        return function == code or (
            function in COMBINED_ARC_FUNCTIONS and code in COMBINED_ARC_FUNCTIONS
        )

    async def _restore_input(self) -> InputRestore:
        """Make sure the soundbar ends up on the input the connection moved."""
        reported = self._initial_function
        sent = self._restored_input
        if reported is None or reported == Function.BLUETOOTH:
            # Moved before answering, or already on Bluetooth: nothing known
            # to go back to.
            return InputRestore(reported, False, None, reported is not None, 0)
        moved = sent is not None or self.state.function == Function.BLUETOOTH
        if not moved:
            return InputRestore(reported, False, None, True, 0)
        # Nothing sent yet only if the move came after the start-up. Flags
        # still unknown then mean the soundbar did not report the one that
        # makes Optical, ARC and eARC one input, so the input's own code is the
        # one to use, as the start-up does.
        code = sent or self._switch_back_code(reported) or reported
        if sent is not None and await self._wait_for_input(code):
            return InputRestore(reported, True, sent, True, 0)
        for attempt in range(1, SWITCH_ATTEMPTS + 1):
            _LOGGER.debug(
                "%s: selecting %02x again (attempt %s)", self.address, code, attempt
            )
            try:
                await self.select_function(code)
            except NotConnected:
                # Dropped meanwhile, as when switched off: the connection
                # worked, so report the restore rather than fail connect().
                _LOGGER.debug(
                    "%s closed the connection while switching back", self.address
                )
                return InputRestore(reported, True, sent, False, attempt - 1)
            if await self._wait_for_input(code):
                return InputRestore(reported, True, sent, True, attempt)
        _LOGGER.debug("%s did not go back to %02x", self.address, code)
        return InputRestore(reported, True, sent, False, SWITCH_ATTEMPTS)

    async def _wait_for_input(self, code: int) -> bool:
        """Wait until the soundbar reports the input a code selects."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._switch_wait
        while loop.time() < deadline and self.connected:
            if self._same_input(self.state.function, code):
                return True
            await asyncio.sleep(0.05)
        return self._same_input(self.state.function, code)

    def _note_boot_state(self, value: int) -> None:
        """Note an MTK start-up state reported while connecting.

        As in the LG app: "started" means the soundbar is still starting up
        and ignores the start-up, so it waits; "completed" means it is ready,
        so the start-up runs again. Unconfirmed on a real soundbar (an LG G1
        has no MTK chip and never sends it).
        """
        if value == MTK_BOOT_STARTED:
            self._mark("starting up")
            self._boot_completed.clear()
            self._boot_reported.set()
        elif value == MTK_BOOT_COMPLETED:
            self._mark("started up")
            self._boot_completed.set()
            self._boot_reported.set()

    def _keep_switched_back(self, function: int) -> None:
        """Select the input switched back to again if the soundbar leaves it.

        After switching back to HDMI, a G1 with a TV on eARC moved itself to
        eARC about a second later; selecting HDMI again stuck. This is done
        once, while the connection is starting up. Optical, ARC and eARC
        count as one input, as a G1 reports Optical then eARC after
        Optical/HDMI ARC is selected. To review: the integration's retry
        restores the input anyway, only later (see docs/PROTOCOL.md).
        """
        code = self._restored_input
        if self._ready or code is None or self._switched_back_again:
            return
        if function == code or (
            function in COMBINED_ARC_FUNCTIONS and code in COMBINED_ARC_FUNCTIONS
        ):
            self._switch_back_reached = True
        elif self._switch_back_reached:
            self._switched_back_again = True
            self._mark("switched back again")
            _LOGGER.debug(
                "%s left the input it was switched back to; selecting %02x again",
                self.address,
                code,
            )
            self._write(
                Frame(Category.GENERAL, GeneralCommand.SET_MODE, bytes((code,)))
            )

    def _switch_back(self, code: int) -> None:
        """Select the input the soundbar was on before it moved."""
        self._moved_from = None
        self._restored_input = code
        self._mark("switched back")
        _LOGGER.debug("%s: selecting %02x again", self.address, code)
        self._write(Frame(Category.GENERAL, GeneralCommand.SET_MODE, bytes((code,))))

    def _attach(
        self, protocol: _SoundbarProtocol, transport: asyncio.BaseTransport
    ) -> float:
        """Take over the connection the connector opened; return when it opened."""
        self._transport = transport  # type: ignore[assignment]
        self._protocol = protocol
        opened_at = self._opened_at = time.monotonic()
        return opened_at

    def _mark(self, step: str) -> None:
        """Record when a handshake step first happened."""
        if self._opened_at is not None and step not in self._timings:
            self._timings[step] = round(time.monotonic() - self._opened_at, 3)

    def _handle_connection_lost(
        self, protocol: _SoundbarProtocol, exc: Exception | None
    ) -> None:
        if protocol is not self._protocol:
            return
        if self._waiting_for is not None and not self._waiting_for[1].done():
            self._waiting_for[1].set_exception(
                NotConnected(f"{self.address} closed the connection")
            )
        was_ready = self._ready
        self._close_reason = exc
        self._last_duration = (
            time.monotonic() - self._ready_at
            if was_ready and self._ready_at is not None
            else None
        )
        self._transport = None
        self._protocol = None
        self._ready = False
        _LOGGER.debug("Connection to %s closed: %r", self.address, exc)
        if was_ready:
            self._notify()

    def _drop_transport(self) -> None:
        transport = self._transport
        self._transport = None
        self._protocol = None
        self._ready = False
        if transport is not None:
            transport.close()

    def _notify(self) -> None:
        for callback in list(self._callbacks):
            try:
                callback()
            except Exception:
                _LOGGER.exception("Error in LG soundbar callback")
