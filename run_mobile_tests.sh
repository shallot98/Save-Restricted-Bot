#!/bin/bash
#
# Mobile Test Runner Script
#
# Usage:
#   ./run_mobile_tests.sh                 # Run all mobile tests
#   ./run_mobile_tests.sh --suite responsive    # Run specific test suite
#   ./run_mobile_tests.sh --coverage      # Run with coverage report
#   ./run_mobile_tests.sh --visual-update # Update visual regression baselines
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
COVERAGE=false
UPDATE_BASELINES=false
SUITE=""
HEADLESS=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --visual-update)
            UPDATE_BASELINES=true
            shift
            ;;
        --suite)
            SUITE="$2"
            shift 2
            ;;
        --headed)
            HEADLESS=false
            shift
            ;;
        --help)
            echo "Mobile Test Runner"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --coverage        Generate coverage report"
            echo "  --visual-update   Update visual regression baselines"
            echo "  --suite NAME      Run specific test suite (responsive|touch|form|performance|api|state|visual)"
            echo "  --headed          Run tests in headed mode (show browser)"
            echo "  --help            Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Mobile Test Suite Runner${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""

# Check if pytest and playwright are installed
if ! python3 -m pip list | grep -q "pytest"; then
    echo -e "${RED}Error: pytest not installed${NC}"
    echo "Run: pip install -r requirements.txt"
    exit 1
fi

if ! python3 -m pip list | grep -q "playwright"; then
    echo -e "${RED}Error: playwright not installed${NC}"
    echo "Run: pip install -r requirements.txt && playwright install"
    exit 1
fi

# Build pytest command
PYTEST_CMD="python3 -m pytest tests/mobile/"

# Add suite filter if specified
if [ -n "$SUITE" ]; then
    echo -e "${YELLOW}Running test suite: $SUITE${NC}"
    PYTEST_CMD="$PYTEST_CMD -k test_$SUITE"
fi

# Add coverage if requested
if [ "$COVERAGE" = true ]; then
    echo -e "${YELLOW}Coverage reporting enabled${NC}"
    PYTEST_CMD="$PYTEST_CMD --cov=templates --cov=app --cov-report=html --cov-report=term"
fi

# Add visual baseline update if requested
if [ "$UPDATE_BASELINES" = true ]; then
    echo -e "${YELLOW}Updating visual regression baselines${NC}"
    PYTEST_CMD="$PYTEST_CMD --screenshot=only-on-failure --update-snapshots"
fi

# Add headless/headed mode
if [ "$HEADLESS" = false ]; then
    PYTEST_CMD="$PYTEST_CMD --headed"
fi

# Run tests
echo -e "${GREEN}Running tests...${NC}"
echo "Command: $PYTEST_CMD"
echo ""

$PYTEST_CMD

EXIT_CODE=$?

# Report results
echo ""
echo -e "${GREEN}==================================${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"

    # Count test results
    TEST_COUNT=$(grep -r "def test_" tests/mobile/*.py | wc -l)
    echo -e "${GREEN}Total test cases: $TEST_COUNT${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo -e "${GREEN}Coverage report generated: htmlcov/index.html${NC}"
    fi
else
    echo -e "${RED}Tests failed with exit code $EXIT_CODE${NC}"
fi
echo -e "${GREEN}==================================${NC}"

exit $EXIT_CODE
