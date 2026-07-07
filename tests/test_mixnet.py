import asyncio
import json
import base64
import pytest
from mixnet import MixNode, OnionRouter


class TestMixNodeInit:
    def test_node_id_stored(self):
        node = MixNode("test_node")
        assert node.node_id == "test_node"

    def test_message_queue_empty(self):
        node = MixNode("n1")
        assert node.message_queue == []

    def test_output_queue_empty(self):
        node = MixNode("n1")
        assert node.output_queue == []

    def test_batch_size_in_range(self):
        for _ in range(20):
            node = MixNode("n")
            assert 5 <= node.batch_size <= 20

    def test_delay_in_range(self):
        for _ in range(20):
            node = MixNode("n")
            assert 0.5 <= node.delay <= 3.0


class TestMixNodeReceiveMessage:
    @pytest.mark.asyncio
    async def test_receive_adds_to_queue(self):
        node = MixNode("n1")
        node.batch_size = 100  # prevent auto-processing
        await node.receive_message("msg1")
        assert len(node.message_queue) == 1

    @pytest.mark.asyncio
    async def test_received_message_has_no_source(self):
        node = MixNode("n1")
        node.batch_size = 100
        await node.receive_message("msg1")
        assert node.message_queue[0]['source'] is None

    @pytest.mark.asyncio
    async def test_received_message_has_timestamp(self):
        node = MixNode("n1")
        node.batch_size = 100
        await node.receive_message("msg1")
        assert 'received' in node.message_queue[0]
        assert isinstance(node.message_queue[0]['received'], float)

    @pytest.mark.asyncio
    async def test_batch_triggers_processing(self):
        node = MixNode("n1")
        node.batch_size = 2
        node.delay = 0.01  # speed up test
        await node.receive_message("msg1")
        assert len(node.message_queue) == 1
        await node.receive_message("msg2")
        # After batch_size reached, queue should be cleared
        assert len(node.message_queue) == 0
        assert len(node.output_queue) == 2


class TestMixNodeProcessBatch:
    @pytest.mark.asyncio
    async def test_process_batch_clears_queue(self):
        node = MixNode("n1")
        node.delay = 0.01
        node.message_queue = [
            {'message': 'a', 'received': 0, 'source': None},
            {'message': 'b', 'received': 0, 'source': None},
        ]
        await node.process_batch()
        assert len(node.message_queue) == 0

    @pytest.mark.asyncio
    async def test_process_batch_fills_output_queue(self):
        node = MixNode("n1")
        node.delay = 0.01
        node.message_queue = [
            {'message': 'a', 'received': 0, 'source': None},
            {'message': 'b', 'received': 0, 'source': None},
        ]
        await node.process_batch()
        assert len(node.output_queue) == 2

    @pytest.mark.asyncio
    async def test_forward_message_returns_same_message(self):
        node = MixNode("n1")
        result = await node.forward_message("payload")
        assert result == "payload"


class TestMixNodeGetMessages:
    @pytest.mark.asyncio
    async def test_get_messages_returns_output(self):
        node = MixNode("n1")
        node.output_queue = ["a", "b"]
        msgs = await node.get_messages()
        assert msgs == ["a", "b"]

    @pytest.mark.asyncio
    async def test_get_messages_clears_output_queue(self):
        node = MixNode("n1")
        node.output_queue = ["a", "b"]
        await node.get_messages()
        assert node.output_queue == []

    @pytest.mark.asyncio
    async def test_get_messages_empty_queue(self):
        node = MixNode("n1")
        msgs = await node.get_messages()
        assert msgs == []


class TestOnionRouterInit:
    def test_nodes_discovered(self):
        router = OnionRouter()
        assert len(router.nodes) == 10

    def test_nodes_named_correctly(self):
        router = OnionRouter()
        for i, n in enumerate(router.nodes):
            assert n == f"node_{i}"

    def test_circuit_initially_empty(self):
        router = OnionRouter()
        assert router.circuit == []


class TestOnionRouterCreateCircuit:
    def test_default_circuit_length_3(self):
        router = OnionRouter()
        circuit = router.create_circuit()
        assert len(circuit) == 3

    def test_custom_circuit_length(self):
        router = OnionRouter()
        circuit = router.create_circuit(length=5)
        assert len(circuit) == 5

    def test_circuit_stored_on_instance(self):
        router = OnionRouter()
        circuit = router.create_circuit()
        assert router.circuit == circuit

    def test_circuit_nodes_are_unique(self):
        router = OnionRouter()
        circuit = router.create_circuit(length=5)
        assert len(set(circuit)) == 5

    def test_circuit_nodes_come_from_discovered_nodes(self):
        router = OnionRouter()
        circuit = router.create_circuit()
        for node in circuit:
            assert node in router.nodes


class TestOnionRouterWrapUnwrap:
    def setup_method(self):
        self.router = OnionRouter()

    def test_wrap_returns_string(self):
        circuit = self.router.create_circuit()
        wrapped = self.router.wrap_message("hello", circuit)
        assert isinstance(wrapped, str)

    def test_wrap_produces_base64(self):
        circuit = self.router.create_circuit()
        wrapped = self.router.wrap_message("hello", circuit)
        # Should be valid base64
        base64.b64decode(wrapped)

    def test_unwrap_peels_one_layer(self):
        circuit = self.router.create_circuit(length=1)
        wrapped = self.router.wrap_message("payload", circuit)
        unwrapped = self.router.unwrap_message(wrapped)
        # With 1 hop, unwrapping once should give us the payload
        assert unwrapped == "payload"

    def test_unwrap_multi_layer(self):
        circuit = self.router.create_circuit(length=3)
        wrapped = self.router.wrap_message("deep_payload", circuit)
        # Peel layers one at a time
        current = wrapped
        for _ in range(3):
            current = self.router.unwrap_message(current)
        assert current == "deep_payload"

    def test_unwrap_invalid_data_returns_input(self):
        result = self.router.unwrap_message("not_base64!!!")
        assert result == "not_base64!!!"

    def test_wrap_with_empty_circuit(self):
        wrapped = self.router.wrap_message("raw", [])
        assert wrapped == "raw"

    def test_wrap_message_contains_next_hop(self):
        circuit = ["node_0"]
        wrapped = self.router.wrap_message("test", circuit)
        decoded = json.loads(base64.b64decode(wrapped))
        assert decoded['next_hop'] == "node_0"
        assert decoded['payload'] == "test"
        assert 'timestamp' in decoded
