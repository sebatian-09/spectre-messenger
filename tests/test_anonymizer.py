import struct
import pytest
from anonymizer import TrafficObfuscator


class TestTrafficObfuscatorInit:
    def test_padding_sizes_set(self):
        obf = TrafficObfuscator()
        assert obf.padding_sizes == [128, 256, 512, 1024, 2048]

    def test_decoy_patterns_generated(self):
        obf = TrafficObfuscator()
        assert len(obf.decoy_patterns) == 1000

    def test_decoy_patterns_are_bytes(self):
        obf = TrafficObfuscator()
        for p in obf.decoy_patterns[:5]:
            assert isinstance(p, bytes)

    def test_decoy_pattern_sizes_within_expected_range(self):
        obf = TrafficObfuscator()
        valid_sizes = {64, 128, 256, 512, 1024}
        for p in obf.decoy_patterns:
            assert len(p) in valid_sizes


class TestObfuscateDeobfuscate:
    def setup_method(self):
        self.obf = TrafficObfuscator()

    def test_obfuscate_returns_bytes(self):
        result = self.obf.obfuscate_packet(b"hello")
        assert isinstance(result, bytes)

    def test_obfuscated_packet_has_4_byte_header(self):
        result = self.obf.obfuscate_packet(b"test")
        pad_size = struct.unpack('!I', result[:4])[0]
        assert pad_size in self.obf.padding_sizes

    def test_roundtrip_preserves_payload(self):
        payload = b"secret message content"
        wrapped = self.obf.obfuscate_packet(payload)
        unwrapped = self.obf.deobfuscate_packet(wrapped)
        assert unwrapped == payload

    def test_roundtrip_empty_payload(self):
        payload = b""
        wrapped = self.obf.obfuscate_packet(payload)
        unwrapped = self.obf.deobfuscate_packet(wrapped)
        assert unwrapped == payload

    def test_roundtrip_large_payload(self):
        payload = b"X" * 5000
        wrapped = self.obf.obfuscate_packet(payload)
        unwrapped = self.obf.deobfuscate_packet(wrapped)
        assert unwrapped == payload

    def test_roundtrip_binary_payload(self):
        payload = bytes(range(256))
        wrapped = self.obf.obfuscate_packet(payload)
        unwrapped = self.obf.deobfuscate_packet(wrapped)
        assert unwrapped == payload

    def test_obfuscated_larger_than_original(self):
        payload = b"small"
        wrapped = self.obf.obfuscate_packet(payload)
        assert len(wrapped) > len(payload)

    def test_different_obfuscations_may_differ(self):
        payload = b"determinism check"
        w1 = self.obf.obfuscate_packet(payload)
        w2 = self.obf.obfuscate_packet(payload)
        # Padding is random, so packets will almost certainly differ
        # (both still deobfuscate to the same payload)
        u1 = self.obf.deobfuscate_packet(w1)
        u2 = self.obf.deobfuscate_packet(w2)
        assert u1 == u2 == payload


class TestDeobfuscateEdgeCases:
    def setup_method(self):
        self.obf = TrafficObfuscator()

    def test_invalid_compressed_data_raises(self):
        bad_packet = struct.pack('!I', 128) + b"not compressed data"
        with pytest.raises(Exception):
            self.obf.deobfuscate_packet(bad_packet)

    def test_zero_padding_size(self):
        import zlib
        payload = b"hello"
        header = struct.pack('!I', 0)
        compressed = zlib.compress(payload)
        packet = header + compressed
        result = self.obf.deobfuscate_packet(packet)
        assert result == payload


class TestDecoyTraffic:
    def setup_method(self):
        self.obf = TrafficObfuscator()

    def test_create_decoy_returns_dict(self):
        decoy = self.obf.create_decoy_traffic()
        assert isinstance(decoy, dict)

    def test_decoy_has_required_keys(self):
        decoy = self.obf.create_decoy_traffic()
        assert 'type' in decoy
        assert 'data' in decoy
        assert 'timestamp' in decoy
        assert 'fake_route' in decoy

    def test_decoy_type_is_decoy(self):
        decoy = self.obf.create_decoy_traffic()
        assert decoy['type'] == 'decoy'

    def test_decoy_data_is_bytes(self):
        decoy = self.obf.create_decoy_traffic()
        assert isinstance(decoy['data'], bytes)

    def test_decoy_timestamp_is_float(self):
        decoy = self.obf.create_decoy_traffic()
        assert isinstance(decoy['timestamp'], float)


class TestFakeRoute:
    def setup_method(self):
        self.obf = TrafficObfuscator()

    def test_fake_route_is_list(self):
        decoy = self.obf.create_decoy_traffic()
        assert isinstance(decoy['fake_route'], list)

    def test_fake_route_has_3_to_8_hops(self):
        for _ in range(20):
            decoy = self.obf.create_decoy_traffic()
            assert 3 <= len(decoy['fake_route']) <= 8

    def test_fake_route_entries_look_like_ips(self):
        decoy = self.obf.create_decoy_traffic()
        for ip in decoy['fake_route']:
            parts = ip.split('.')
            assert len(parts) == 4
            for octet in parts:
                assert 1 <= int(octet) <= 255
