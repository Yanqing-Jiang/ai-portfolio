#!/usr/bin/env python3
"""
Comprehensive Test Suite for ConfigStore

Tests all ConfigStore functionality including:
- Unified interface operations
- Fallback chain behavior
- Error handling and recovery
- Performance characteristics
- Caching behavior
- Integration with existing services
"""

import asyncio
import time
import os
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, Any, List

# Setup path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics_supervisor.config_store import (
    ConfigStore, ConfigResult, ConfigSource, QueryType, FallbackConfig,
    get_config_store, close_config_store
)


class TestConfigStoreCore:
    """Test core ConfigStore functionality"""

    def setup_method(self):
        """Setup for each test method"""
        self.config_store = ConfigStore()

    async def test_templates_fallback_chain(self):
        """Test template retrieval with complete fallback chain"""
        # Test case 1: RAG service succeeds
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()
            mock_rag_service.search_templates.return_value = [
                Mock(id='1', title='Test Template', description='Test', content={'intent_key': 'test'},
                     score=0.9, distance=0.1, source_table='sql_templates')
            ]
            mock_rag.return_value = mock_rag_service

            result = await self.config_store.get_templates("revenue analysis")

            assert result.success
            assert result.source == ConfigSource.RAG_SERVICE
            assert len(result.data) == 1
            assert result.data[0]['title'] == 'Test Template'
            assert result.query_time_ms > 0

    async def test_templates_rag_failure_template_store_success(self):
        """Test template fallback from RAG to template store"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag, \
             patch('analytics_supervisor.config_store.search_templates') as mock_search:

            # RAG service fails
            mock_rag.side_effect = Exception("RAG service unavailable")

            # Template store succeeds
            mock_search.return_value = [{'id': '1', 'name': 'Template from store'}]

            result = await self.config_store.get_templates("revenue analysis")

            assert result.success
            assert result.source == ConfigSource.TEMPLATE_STORE
            assert ConfigSource.RAG_SERVICE in result.fallback_attempted
            assert len(result.data) == 1

    async def test_templates_all_fallback_to_yaml(self):
        """Test template fallback to YAML config"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag, \
             patch('analytics_supervisor.config_store.search_templates') as mock_search:

            # RAG service fails
            mock_rag.side_effect = Exception("RAG service unavailable")

            # Template store fails
            mock_search.side_effect = Exception("Template store unavailable")

            # YAML config has matching pattern
            self.config_store.yaml_configs = {
                'query_patterns': {
                    'revenue_analysis': {
                        'name': 'Revenue Analysis',
                        'description': 'Analyze revenue trends',
                        'sql_template': 'SELECT * FROM revenue',
                        'keywords': ['revenue', 'analysis']
                    }
                }
            }

            result = await self.config_store.get_templates("revenue analysis")

            assert result.success
            assert result.source == ConfigSource.YAML_CONFIG
            assert ConfigSource.RAG_SERVICE in result.fallback_attempted
            assert ConfigSource.TEMPLATE_STORE in result.fallback_attempted
            assert len(result.data) == 1
            assert result.data[0]['name'] == 'Revenue Analysis'

    async def test_templates_empty_fallback(self):
        """Test empty fallback when all sources fail"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag, \
             patch('analytics_supervisor.config_store.search_templates') as mock_search:

            # All sources fail
            mock_rag.side_effect = Exception("RAG service unavailable")
            mock_search.side_effect = Exception("Template store unavailable")
            self.config_store.yaml_configs = {}

            result = await self.config_store.get_templates("revenue analysis")

            assert not result.success
            assert result.source == ConfigSource.EMPTY_FALLBACK
            assert len(result.data) == 0
            assert result.error is not None
            assert len(result.fallback_attempted) >= 2

    async def test_metrics_search_success(self):
        """Test metrics search with RAG success"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()
            mock_rag_service.search_metrics.return_value = [
                Mock(id='revenue', title='Revenue', description='Company revenue',
                     content={'category_id': 'income_statement'}, score=0.95,
                     distance=0.05, source_table='metrics')
            ]
            mock_rag.return_value = mock_rag_service

            result = await self.config_store.get_metrics("revenue", top_k=5)

            assert result.success
            assert result.source == ConfigSource.RAG_SERVICE
            assert len(result.data) == 1
            assert result.data[0]['title'] == 'Revenue'

    async def test_metrics_yaml_fallback(self):
        """Test metrics fallback to YAML config"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            # RAG service fails
            mock_rag.side_effect = Exception("RAG service unavailable")

            # YAML config has matching metrics
            self.config_store.yaml_configs = {
                'metrics': {
                    'base_metrics': [
                        {
                            'name': 'Revenue',
                            'description': 'Total revenue',
                            'metric_id': 'revenue',
                            'category': 'income_statement',
                            'aliases': ['sales', 'turnover']
                        }
                    ]
                }
            }

            result = await self.config_store.get_metrics("revenue")

            assert result.success
            assert result.source == ConfigSource.YAML_CONFIG
            assert len(result.data) == 1
            assert result.data[0]['name'] == 'Revenue'

    async def test_companies_search_success(self):
        """Test companies search with RAG success"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()
            mock_rag_service.search_companies.return_value = [
                Mock(id='NVDA', title='Nvidia Corporation', description='GPU manufacturer',
                     content={'ticker': 'NVDA', 'sector': 'semiconductor'},
                     score=0.98, distance=0.02, source_table='companies')
            ]
            mock_rag.return_value = mock_rag_service

            result = await self.config_store.get_companies("nvidia")

            assert result.success
            assert result.source == ConfigSource.RAG_SERVICE
            assert len(result.data) == 1
            assert result.data[0]['title'] == 'Nvidia Corporation'

    async def test_companies_yaml_fallback(self):
        """Test companies fallback to YAML config"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            # RAG service fails
            mock_rag.side_effect = Exception("RAG service unavailable")

            # YAML config has matching companies
            self.config_store.yaml_configs = {
                'companies': {
                    'semiconductor': {
                        'companies': [
                            {
                                'name': 'Nvidia Corporation',
                                'short_name': 'Nvidia',
                                'ticker': 'NVDA',
                                'sector': 'semiconductor',
                                'aliases': ['nvidia', 'nvda']
                            }
                        ]
                    }
                }
            }

            result = await self.config_store.get_companies("nvidia")

            assert result.success
            assert result.source == ConfigSource.YAML_CONFIG
            assert len(result.data) == 1
            assert result.data[0]['name'] == 'Nvidia Corporation'

    async def test_analytics_context_success(self):
        """Test comprehensive analytics context retrieval"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()
            mock_rag_service.get_analytics_context.return_value = {
                'templates': [{'name': 'Revenue Analysis'}],
                'metrics': [{'name': 'Revenue'}],
                'companies': [{'name': 'Nvidia'}],
                'related_items': {}
            }
            mock_rag.return_value = mock_rag_service

            result = await self.config_store.get_analytics_context("nvidia revenue analysis")

            assert result.success
            assert result.source == ConfigSource.RAG_SERVICE
            assert len(result.data) == 1
            context = result.data[0]
            assert 'templates' in context
            assert 'metrics' in context
            assert 'companies' in context


class TestConfigStoreCaching:
    """Test ConfigStore caching behavior"""

    def setup_method(self):
        """Setup for each test method"""
        self.config_store = ConfigStore()

    async def test_cache_hit_behavior(self):
        """Test that cache returns previous results"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()
            mock_rag_service.search_templates.return_value = [
                Mock(id='1', title='Cached Template', description='Test',
                     content={'intent_key': 'test'}, score=0.9, distance=0.1,
                     source_table='sql_templates')
            ]
            mock_rag.return_value = mock_rag_service

            # First call
            result1 = await self.config_store.get_templates("test query")
            assert result1.success
            assert not result1.cache_hit

            # Second call should hit cache
            result2 = await self.config_store.get_templates("test query")
            assert result2.success
            assert result2.cache_hit

            # Verify RAG service was only called once
            assert mock_rag_service.search_templates.call_count == 1

    def test_cache_key_generation(self):
        """Test cache key generation for different query types"""
        key1 = self.config_store._cache_key(QueryType.TEMPLATES, "test", intent_key="analysis")
        key2 = self.config_store._cache_key(QueryType.TEMPLATES, "test", intent_key="overview")
        key3 = self.config_store._cache_key(QueryType.METRICS, "test", intent_key="analysis")

        assert key1 != key2  # Different parameters
        assert key1 != key3  # Different query types
        assert key2 != key3  # Different types and parameters

    def test_cache_expiry(self):
        """Test cache expiry behavior"""
        # Test with very short TTL
        self.config_store._cache_ttl = 0.001  # 1ms

        # Add item to cache
        timestamp = time.time()
        self.config_store._cache['test_key'] = (timestamp, 'test_value')

        # Should be valid immediately
        assert self.config_store._is_cache_valid(timestamp)

        # Wait for expiry
        time.sleep(0.002)

        # Should be expired
        assert not self.config_store._is_cache_valid(timestamp)

    def test_cache_clear(self):
        """Test cache clearing functionality"""
        # Add items to cache
        self.config_store._cache['key1'] = (time.time(), 'value1')
        self.config_store._cache['key2'] = (time.time(), 'value2')

        assert len(self.config_store._cache) == 2

        # Clear cache
        cleared_count = self.config_store.clear_cache()

        assert cleared_count == 2
        assert len(self.config_store._cache) == 0


class TestConfigStoreFallbackConfig:
    """Test ConfigStore fallback configuration"""

    def test_fallback_config_default(self):
        """Test default fallback configuration"""
        config_store = ConfigStore()

        assert config_store.fallback_config.enable_rag
        assert config_store.fallback_config.enable_template_store
        assert config_store.fallback_config.enable_yaml_config
        assert config_store.fallback_config.timeout_rag_ms == 5000
        assert config_store.fallback_config.timeout_template_store_ms == 3000

    def test_fallback_config_custom(self):
        """Test custom fallback configuration"""
        custom_config = FallbackConfig(
            enable_rag=False,
            enable_template_store=True,
            timeout_rag_ms=1000
        )

        config_store = ConfigStore(custom_config)

        assert not config_store.fallback_config.enable_rag
        assert config_store.fallback_config.enable_template_store
        assert config_store.fallback_config.timeout_rag_ms == 1000

    async def test_rag_disabled_skips_to_template_store(self):
        """Test that disabling RAG skips directly to template store"""
        custom_config = FallbackConfig(enable_rag=False)
        config_store = ConfigStore(custom_config)

        with patch('analytics_supervisor.config_store.search_templates') as mock_search:
            mock_search.return_value = [{'id': '1', 'name': 'Template from store'}]

            result = await config_store.get_templates("test query")

            assert result.success
            assert result.source == ConfigSource.TEMPLATE_STORE
            # RAG should not be in fallback attempts since it's disabled
            assert ConfigSource.RAG_SERVICE not in result.fallback_attempted


class TestConfigStoreIntegration:
    """Test ConfigStore integration with existing services"""

    async def test_integration_with_supervisor_tools(self):
        """Test ConfigStore integration with SupervisorTools"""
        from analytics_supervisor.tools import SupervisorTools

        tools = SupervisorTools()

        # Verify ConfigStore is initialized
        assert hasattr(tools, 'config_store')
        assert isinstance(tools.config_store, ConfigStore)

    async def test_get_system_stats(self):
        """Test system statistics functionality"""
        config_store = ConfigStore()

        stats = await config_store.get_system_stats()

        assert 'cache_size' in stats
        assert 'fallback_config' in stats
        assert 'sources_available' in stats
        assert isinstance(stats['sources_available'], list)

    async def test_close_config_store(self):
        """Test ConfigStore cleanup on close"""
        config_store = ConfigStore()

        # Add some cache items
        config_store._cache['test'] = (time.time(), 'value')

        await config_store.close()

        # Cache should be cleared
        assert len(config_store._cache) == 0


class TestConfigStoreErrorHandling:
    """Test ConfigStore error handling and recovery"""

    def setup_method(self):
        """Setup for each test method"""
        self.config_store = ConfigStore()

    async def test_timeout_handling(self):
        """Test timeout handling in fallback chain"""
        # Mock a slow RAG service
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()

            async def slow_search(*args, **kwargs):
                await asyncio.sleep(10)  # Longer than timeout
                return []

            mock_rag_service.search_templates = slow_search
            mock_rag.return_value = mock_rag_service

            # Set short timeout for testing
            self.config_store.fallback_config.timeout_rag_ms = 100

            start_time = time.time()
            result = await self.config_store.get_templates("test query")
            elapsed_time = time.time() - start_time

            # Should timeout quickly and fallback
            assert elapsed_time < 1.0  # Much less than the 10s sleep
            assert ConfigSource.RAG_SERVICE in result.fallback_attempted

    async def test_exception_propagation(self):
        """Test that exceptions are properly caught and logged"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            # Simulate a severe error that propagates
            mock_rag.side_effect = RuntimeError("Critical system error")

            result = await self.config_store.get_templates("test query")

            # Should gracefully handle the error
            assert ConfigSource.RAG_SERVICE in result.fallback_attempted
            assert result.error is not None


class TestConfigResultDataClass:
    """Test ConfigResult dataclass functionality"""

    def test_config_result_success_property(self):
        """Test ConfigResult success property logic"""
        # Successful result
        result_success = ConfigResult(
            data=[{'name': 'test'}],
            source=ConfigSource.RAG_SERVICE,
            query_time_ms=100.0,
            total_results=1
        )
        assert result_success.success

        # Empty result
        result_empty = ConfigResult(
            data=[],
            source=ConfigSource.EMPTY_FALLBACK,
            query_time_ms=100.0,
            total_results=0
        )
        assert not result_empty.success

        # Error result
        result_error = ConfigResult(
            data=[],
            source=ConfigSource.RAG_SERVICE,
            query_time_ms=100.0,
            total_results=0,
            error="Something went wrong"
        )
        assert not result_error.success

    def test_config_result_empty_fallback_property(self):
        """Test ConfigResult empty fallback detection"""
        result_empty = ConfigResult(
            data=[],
            source=ConfigSource.EMPTY_FALLBACK,
            query_time_ms=100.0,
            total_results=0
        )
        assert result_empty.is_empty_fallback

        result_rag = ConfigResult(
            data=[{'name': 'test'}],
            source=ConfigSource.RAG_SERVICE,
            query_time_ms=100.0,
            total_results=1
        )
        assert not result_rag.is_empty_fallback


class TestGlobalConfigStore:
    """Test global ConfigStore instance management"""

    def test_get_config_store_singleton(self):
        """Test that get_config_store returns singleton instance"""
        store1 = get_config_store()
        store2 = get_config_store()

        assert store1 is store2

    async def test_close_config_store_global(self):
        """Test global ConfigStore cleanup"""
        store = get_config_store()
        assert store is not None

        await close_config_store()

        # Should create new instance after close
        new_store = get_config_store()
        assert new_store is not store


# Performance and Load Testing
class TestConfigStorePerformance:
    """Test ConfigStore performance characteristics"""

    def setup_method(self):
        """Setup for each test method"""
        self.config_store = ConfigStore()

    async def test_concurrent_requests(self):
        """Test ConfigStore behavior under concurrent load"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()
            mock_rag_service.search_templates.return_value = [
                Mock(id='1', title='Template', description='Test',
                     content={'intent_key': 'test'}, score=0.9, distance=0.1,
                     source_table='sql_templates')
            ]
            mock_rag.return_value = mock_rag_service

            # Create multiple concurrent requests
            tasks = []
            for i in range(10):
                task = self.config_store.get_templates(f"query {i}")
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # All requests should succeed
            assert all(result.success for result in results)
            assert len(results) == 10

    async def test_query_performance_timing(self):
        """Test that query performance is tracked accurately"""
        with patch.object(self.config_store, '_get_rag_service') as mock_rag:
            mock_rag_service = AsyncMock()

            async def timed_search(*args, **kwargs):
                await asyncio.sleep(0.1)  # 100ms delay
                return [Mock(id='1', title='Template', description='Test',
                           content={'intent_key': 'test'}, score=0.9, distance=0.1,
                           source_table='sql_templates')]

            mock_rag_service.search_templates = timed_search
            mock_rag.return_value = mock_rag_service

            result = await self.config_store.get_templates("test query")

            # Query time should be approximately 100ms
            assert result.query_time_ms >= 100
            assert result.query_time_ms < 200  # Allow some overhead


if __name__ == "__main__":
    # Simple test runner
    async def run_basic_tests():
        """Run basic ConfigStore tests"""
        print("Running ConfigStore Tests...")

        # Test basic functionality
        test_core = TestConfigStoreCore()
        test_core.setup_method()

        try:
            await test_core.test_templates_fallback_chain()
            print("[PASS] Template fallback chain test passed")

            await test_core.test_templates_rag_failure_template_store_success()
            print("[PASS] Template RAG failure fallback test passed")

            await test_core.test_metrics_search_success()
            print("[PASS] Metrics search test passed")

            await test_core.test_companies_search_success()
            print("[PASS] Companies search test passed")

        except Exception as e:
            print(f"[FAIL] Test failed: {e}")

        # Test caching
        test_cache = TestConfigStoreCaching()
        test_cache.setup_method()

        try:
            await test_cache.test_cache_hit_behavior()
            print("[PASS] Cache hit behavior test passed")

            test_cache.test_cache_key_generation()
            print("[PASS] Cache key generation test passed")

        except Exception as e:
            print(f"[FAIL] Cache test failed: {e}")

        print("ConfigStore tests completed!")

    # Run tests if called directly
    asyncio.run(run_basic_tests())