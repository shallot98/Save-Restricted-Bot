#!/usr/bin/env python3
"""
Simple Performance Test Runner
Tests critical performance metrics for the bot
"""
import time
import sys
import os
import queue
import threading
import gc
import resource

# Add project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

# Import modules after path setup
from config import load_config, load_watch_config, build_monitored_sources
from bot.filters.keyword import check_whitelist, check_blacklist
from bot.filters.regex import check_whitelist_regex, check_blacklist_regex
from bot.filters.extract import extract_content
from bot.utils.dedup import (
    mark_message_processed, 
    is_message_processed, 
    register_processed_media_group, 
    is_media_group_processed
)
from bot.utils.status import set_user_state, get_user_state, update_user_state, clear_user_state
from bot.workers.message_worker import Message, MessageWorker
from constants import *


def get_memory_mb():
    """Get current memory usage in MB"""
    try:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except:
        return 0


def measure_time(func, *args, **kwargs):
    """Measure function execution time"""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    end = time.perf_counter()
    return result, (end - start) * 1000  # ms


def run_benchmark(name, func, iterations=1000, warmup=10):
    """Run performance benchmark"""
    print(f"\n{'='*60}")
    print(f"🔥 {name}")
    print(f"{'='*60}")
    
    # Warmup
    for _ in range(warmup):
        try:
            func()
        except:
            pass
    
    # Benchmark
    times = []
    for _ in range(iterations):
        try:
            _, exec_time = measure_time(func)
            times.append(exec_time)
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    if not times:
        print("❌ All iterations failed")
        return None
    
    # Statistics
    avg_time = sum(times) / len(times)
    min_time = min(times)
    max_time = max(times)
    
    print(f"迭代次数: {iterations}")
    print(f"平均时间: {avg_time:.4f} ms")
    print(f"最小时间: {min_time:.4f} ms")
    print(f"最大时间: {max_time:.4f} ms")
    print(f"吞吐量:   {1000/avg_time:.2f} ops/sec")
    
    return {
        'name': name,
        'iterations': iterations,
        'avg_ms': avg_time,
        'min_ms': min_time,
        'max_ms': max_time,
        'throughput': 1000/avg_time
    }


def test_filter_performance():
    """Test filter performance"""
    test_text = "Hello world, this is a test message with price 100 USD and email test@example.com"
    whitelist = ["hello", "test", "message"]
    blacklist = ["spam", "bad", "forbidden"]
    whitelist_regex = [r"\d+\s+USD", r"test"]
    blacklist_regex = [r"spam", r"forbidden"]
    extract_patterns = [r"\d+", r"\w+@\w+\.\w+"]
    
    results = []
    
    result = run_benchmark(
        "关键词白名单过滤 (Keyword Whitelist)",
        lambda: check_whitelist(test_text, whitelist),
        iterations=10000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "关键词黑名单过滤 (Keyword Blacklist)",
        lambda: check_blacklist(test_text, blacklist),
        iterations=10000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "正则白名单过滤 (Regex Whitelist)",
        lambda: check_whitelist_regex(test_text, whitelist_regex),
        iterations=5000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "正则黑名单过滤 (Regex Blacklist)",
        lambda: check_blacklist_regex(test_text, blacklist_regex),
        iterations=5000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "内容提取 (Content Extraction)",
        lambda: extract_content(test_text, extract_patterns),
        iterations=5000
    )
    if result:
        results.append(result)
    
    return results


def test_deduplication_performance():
    """Test deduplication performance"""
    results = []
    
    result = run_benchmark(
        "标记消息已处理 (Mark Message Processed)",
        lambda: mark_message_processed(123456, -100123456789),
        iterations=10000
    )
    if result:
        results.append(result)
    
    # Prepare for lookup test
    for i in range(1000):
        mark_message_processed(i, -100123456789)
    
    result = run_benchmark(
        "检查消息是否已处理 (Check Message Processed)",
        lambda: is_message_processed(500, -100123456789),
        iterations=10000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "注册媒体组 (Register Media Group)",
        lambda: register_processed_media_group(f"user_key_dest_forward_{time.time()}"),
        iterations=5000
    )
    if result:
        results.append(result)
    
    return results


def test_config_performance():
    """Test config management performance"""
    results = []
    
    result = run_benchmark(
        "加载主配置 (Load Config)",
        lambda: load_config(),
        iterations=1000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "加载监控配置 (Load Watch Config)",
        lambda: load_watch_config(),
        iterations=1000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "构建监控源集合 (Build Monitored Sources)",
        lambda: build_monitored_sources(),
        iterations=1000
    )
    if result:
        results.append(result)
    
    return results


def test_state_management_performance():
    """Test state management performance"""
    results = []
    
    result = run_benchmark(
        "设置用户状态 (Set User State)",
        lambda: set_user_state("user123", {"step": "test", "data": "value"}),
        iterations=10000
    )
    if result:
        results.append(result)
    
    # Prepare data for get test
    set_user_state("user123", {"step": "test"})
    
    result = run_benchmark(
        "获取用户状态 (Get User State)",
        lambda: get_user_state("user123"),
        iterations=10000
    )
    if result:
        results.append(result)
    
    result = run_benchmark(
        "更新用户状态 (Update User State)",
        lambda: update_user_state("user123", new_field="value"),
        iterations=10000
    )
    if result:
        results.append(result)
    
    return results


def test_queue_performance():
    """Test queue performance"""
    print("\n" + "="*60)
    print("📬 队列性能测试")
    print("="*60)
    
    q = queue.Queue()
    
    # Test enqueue
    _, enqueue_time = measure_time(lambda: [q.put(i) for i in range(1000)])
    print(f"入队1000条消息: {enqueue_time:.4f} ms ({1000000/enqueue_time:.0f} ops/sec)")
    
    # Test dequeue
    _, dequeue_time = measure_time(lambda: [q.get() for _ in range(1000)])
    print(f"出队1000条消息: {dequeue_time:.4f} ms ({1000000/dequeue_time:.0f} ops/sec)")
    
    return {
        'enqueue_ms': enqueue_time,
        'dequeue_ms': dequeue_time,
        'enqueue_ops': 1000000/enqueue_time,
        'dequeue_ops': 1000000/dequeue_time
    }


def test_constants_access():
    """Test constants access performance"""
    print("\n" + "="*60)
    print("🔧 常量访问性能测试")
    print("="*60)
    
    results = []
    
    # Test constant access
    result = run_benchmark(
        "常量访问 (Constant Access)",
        lambda: (MAX_RETRIES, MAX_FLOOD_RETRIES, OPERATION_TIMEOUT),
        iterations=100000
    )
    if result:
        results.append(result)
    
    # Test backoff calculation
    result = run_benchmark(
        "退避计算 (Backoff Calculation)",
        lambda: get_backoff_time(2),
        iterations=100000
    )
    if result:
        results.append(result)
    
    return results


def generate_report(results):
    """Generate performance test report"""
    print("\n" + "="*60)
    print("📊 性能测试总结报告")
    print("="*60)
    
    print("\n🎯 关键性能指标 (Key Performance Indicators)")
    print("-" * 60)
    
    if 'filters' in results and results['filters']:
        print("\n🔍 过滤器性能:")
        for r in results['filters']:
            print(f"  {r['name']:40s} {r['avg_ms']:8.4f} ms/op")
    
    if 'dedup' in results and results['dedup']:
        print("\n🔄 去重性能:")
        for r in results['dedup']:
            print(f"  {r['name']:40s} {r['avg_ms']:8.4f} ms/op")
    
    if 'config' in results and results['config']:
        print("\n⚙️  配置管理性能:")
        for r in results['config']:
            print(f"  {r['name']:40s} {r['avg_ms']:8.4f} ms/op")
    
    if 'state' in results and results['state']:
        print("\n📝 状态管理性能:")
        for r in results['state']:
            print(f"  {r['name']:40s} {r['avg_ms']:8.4f} ms/op")
    
    if 'queue' in results:
        print(f"\n📬 队列性能:")
        print(f"  入队吞吐量: {results['queue']['enqueue_ops']:.0f} ops/sec")
        print(f"  出队吞吐量: {results['queue']['dequeue_ops']:.0f} ops/sec")
    
    if 'constants' in results and results['constants']:
        print(f"\n🔧 常量访问性能:")
        for r in results['constants']:
            print(f"  {r['name']:40s} {r['avg_ms']:8.6f} ms/op ({r['throughput']:.0f} ops/sec)")
    
    print("\n" + "="*60)
    print("✅ 性能测试完成！")
    print("="*60)


def main():
    """Run all performance tests"""
    print("\n" + "="*60)
    print("🚀 Save-Restricted-Bot 性能测试套件")
    print("   Performance Testing Suite")
    print("="*60)
    
    results = {}
    
    try:
        # Filter performance
        print("\n[1/6] 测试过滤器性能...")
        results['filters'] = test_filter_performance()
        
        # Deduplication performance
        print("\n[2/6] 测试去重性能...")
        results['dedup'] = test_deduplication_performance()
        
        # Config performance
        print("\n[3/6] 测试配置管理性能...")
        results['config'] = test_config_performance()
        
        # State management performance
        print("\n[4/6] 测试状态管理性能...")
        results['state'] = test_state_management_performance()
        
        # Queue performance
        print("\n[5/6] 测试队列性能...")
        results['queue'] = test_queue_performance()
        
        # Constants access performance
        print("\n[6/6] 测试常量访问性能...")
        results['constants'] = test_constants_access()
        
        # Generate report
        generate_report(results)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
