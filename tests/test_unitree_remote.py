"""Unitree RC packet contracts in memory; no device, DDS or native thread."""

import struct
import unittest
from queue import Queue

from robojudo.controller.utils.joystick import unitreeRemoteController


def packet(*, keys=0, axes=(0.25, -0.5, 0.75, -1.0)):
    payload = bytearray(40)
    struct.pack_into("<H", payload, 2, keys)
    for offset, value in zip((4, 8, 12, 20), axes, strict=True):
        struct.pack_into("<f", payload, offset, value)
    return bytes(payload)


class UnitreeRemoteTest(unittest.TestCase):
    def setUp(self):
        self.states = Queue(maxsize=1)
        self.events = Queue()
        self.parser = unitreeRemoteController(self.states, self.events)

    def test_axis_packet_layout_and_latest_sample(self):
        self.parser.parse(packet())
        self.assertEqual(
            self.states.get_nowait()["axes"],
            {"LeftX": 0.25, "RightX": -0.5, "RightY": 0.75, "LeftY": -1.0},
        )
        self.parser.parse(packet())
        self.parser.parse(packet(axes=(0.0, 0.0, 0.0, 0.0)))
        self.assertEqual(self.states.qsize(), 1)
        self.assertTrue(all(value == 0.0 for value in self.states.get_nowait()["axes"].values()))
        self.assertTrue(self.events.empty())

    def test_button_press_hold_and_release_edges(self):
        pressed = packet(keys=(1 << 0) | (1 << 8))
        self.parser.parse(pressed)
        self.assertEqual(
            [(event["name"], event["pressed"]) for event in (self.events.get_nowait(), self.events.get_nowait())],
            [("R1", True), ("A", True)],
        )
        self.parser.parse(pressed)
        self.assertTrue(self.events.empty())
        self.parser.parse(packet(keys=0))
        released = [self.events.get_nowait() for _ in range(2)]
        self.assertEqual([(event["name"], event["pressed"]) for event in released], [("R1", False), ("A", False)])
        self.assertTrue(self.events.empty())


if __name__ == "__main__":
    unittest.main()
