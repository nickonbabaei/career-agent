import unittest
from unittest.mock import Mock, patch
from agent.research_runtime import Runtime, ResearchError, ServiceUnavailable

class ServiceRetryTests(unittest.TestCase):
    def test_transient_failure_waits_and_recovers(self):
        operation = Mock(side_effect=[ServiceUnavailable(), 'ok'])
        with patch('agent.research_runtime.time.sleep') as sleep:
            self.assertEqual(Runtime().call(operation, [], 'research', ResearchError), 'ok')
        sleep.assert_called_once_with(15)
        self.assertEqual(operation.call_count, 2)

    def test_persistent_failure_stops_after_one_retry(self):
        operation = Mock(side_effect=ServiceUnavailable())
        with patch('agent.research_runtime.time.sleep'), self.assertRaises(ServiceUnavailable):
            Runtime().call(operation, [], 'research', ResearchError)
        self.assertEqual(operation.call_count, 2)

    def test_long_provider_delay_does_not_retry_early(self):
        operation = Mock(side_effect=ServiceUnavailable(120))
        with patch('agent.research_runtime.time.sleep') as sleep, self.assertRaises(ServiceUnavailable):
            Runtime().call(operation, [], 'research', ResearchError)
        sleep.assert_not_called()
        operation.assert_called_once()
