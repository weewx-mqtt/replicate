#
#    Copyright (c) 2026 Rich Bell <bellrichm@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#

# pylint: disable=missing-module-docstring, missing-class-docstring, missing-function-docstring

import subprocess
import sys
import unittest
from pathlib import Path

import helpers

SCRIPT = Path(__file__).resolve().parents[4] / 'bin' / 'user' / 'run_mqttreplicate.py'

class TestRunMQTTReplicate(unittest.TestCase):
    def run_standalone(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              check=True, capture_output=True, text=True, timeout=30)

    def test_requester_help(self):
        result = self.run_standalone('requester', '--help')
        self.assertIn('Run MQTTReplicate as a requester in standalone mode.', result.stdout)
        self.assertNotIn('ToDo', result.stdout)

    def test_responder_help(self):
        result = self.run_standalone('responder', '--help')
        self.assertIn('Run MQTTReplicate as a responder in standalone mode.', result.stdout)
        self.assertNotIn('ToDo', result.stdout)

if __name__ == '__main__':
    helpers.run_tests()
