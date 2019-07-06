import serial
from thonny.plugins.micropython.connection import MicroPythonConnection, ConnectionFailedException
import threading
import time
from serial.serialutil import SerialException
import logging
import platform
from textwrap import dedent


class SerialConnection(MicroPythonConnection):
    def __init__(self, port, baudrate):
        super().__init__()

        try:
            self._serial = serial.Serial(port, baudrate=baudrate, timeout=None)
        except SerialException as error:
            message = "Unable to connect to " + port + "\n" + "Error: " + str(error)

            # TODO: check if these error codes also apply to Linux and Mac
            if error.errno == 13 and platform.system() == "Linux":
                # TODO: check if user already has this group
                message += "\n\n" + dedent(
                    """\
                Try adding yourself to the 'dialout' group:
                > sudo usermod -a -G dialout <username>
                (NB! This needs to be followed by reboot or logging out and logging in again!)"""
                )

            elif "PermissionError" in message:
                message += "\n\n" + dedent(
                    """\
                If you have serial connection to the device from another program,
                then disconnect it there."""
                )

            elif error.errno == 16:
                message += "\n\n" + "Try restarting the device."

            raise ConnectionFailedException(message)

        self._reading_thread = threading.Thread(target=self._listen_serial, daemon=True)
        self._reading_thread.start()

    def write(self, data, block_size=32, delay=0.01):
        for i in range(0, len(data), block_size):
            block = data[i : i + block_size]
            # self._log_data(b"[" + block + b"]")
            size = self._serial.write(block)
            assert size == len(block)
            time.sleep(delay)
        return len(data)

    def _listen_serial(self):
        "NB! works in background thread"
        try:
            while True:
                b = self._serial.read(1)  # To avoid busy loop
                if len(b) == 0:
                    self._error = "EOF"
                    # print("LISTEN EOFFFFFFFFFF")
                    break
                data = b + self._serial.read_all()
                self.num_bytes_received += len(data)
                self._read_queue.put(data)
                # self._log_data(data)

        except SerialException as e:
            logging.exception("Error while reading from serial")
            self._error = str("Serial reading error: %s" % e)

    def incoming_is_empty(self):
        return self._serial.in_waiting == 0 and super().incoming_is_empty()

    def outgoing_is_empty(self):
        return self._serial.out_waiting == 0

    def reset_output_buffer(self):
        self._serial.reset_output_buffer()

    def close(self):
        if self._serial is not None:
            try:
                self._serial.cancel_read()
                self._reading_thread.join()
            finally:
                try:
                    self._serial.close()
                    self._serial = None
                except Exception:
                    logging.exception("Couldn't close serial")
