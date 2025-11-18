#!/bin/bash
# 运行性能测试套件
# Run Performance Test Suite

set -e

echo "======================================================================"
echo "   Save-Restricted-Bot 性能测试套件"
echo "   Performance Testing Suite"
echo "======================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test 1: Main Performance Tests
echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${YELLOW}📊 [1/2] 运行主要性能测试...${NC}"
echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if python3 tests/run_performance_tests.py; then
    echo ""
    echo "${GREEN}✅ 主要性能测试完成${NC}"
else
    echo ""
    echo "${YELLOW}⚠️  主要性能测试失败，但继续执行...${NC}"
fi

echo ""
echo ""

# Test 2: Performance Comparison
echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${YELLOW}📈 [2/2] 运行性能对比测试...${NC}"
echo "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if python3 tests/performance_comparison.py; then
    echo ""
    echo "${GREEN}✅ 性能对比测试完成${NC}"
else
    echo ""
    echo "${YELLOW}⚠️  性能对比测试失败，但继续执行...${NC}"
fi

echo ""
echo ""

# Summary
echo "======================================================================"
echo "${GREEN}   🎉 性能测试套件执行完成！${NC}"
echo "======================================================================"
echo ""
echo "📋 测试结果总结:"
echo "   • 主要性能测试: 测试核心操作的性能指标"
echo "   • 性能对比测试: 展示优化前后的改进"
echo ""
echo "📁 详细文档:"
echo "   • tests/README_PERFORMANCE.md - 性能测试文档"
echo "   • OPTIMIZATION_QUICK_REFERENCE.md - 优化速查表"
echo ""
echo "💡 提示:"
echo "   建议在生产环境部署前运行性能测试，确保性能符合预期。"
echo ""
