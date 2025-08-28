#!/bin/bash

# NimbleTools Core Project Validation Script
# Validates the project structure, files, and configurations

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validation results
VALIDATIONS_PASSED=0
VALIDATIONS_FAILED=0
FAILED_VALIDATIONS=()

validation_result() {
    local validation_name=$1
    local result=$2
    
    if [[ "$result" == "PASS" ]]; then
        VALIDATIONS_PASSED=$((VALIDATIONS_PASSED + 1))
        log_success "✓ $validation_name"
    else
        VALIDATIONS_FAILED=$((VALIDATIONS_FAILED + 1))
        FAILED_VALIDATIONS+=("$validation_name")
        log_error "✗ $validation_name"
    fi
}

# File existence checks
validate_required_files() {
    log_info "Validating required files..."
    
    local required_files=(
        "README.md"
        "LICENSE"
        "CONTRIBUTING.md"
        "CHANGELOG.md"
        "install.sh"
        "universal-adapter/main.py"
        "universal-adapter/Dockerfile"
        "universal-adapter/requirements.txt"
        "universal-adapter/README.md"
        "operator/main.py"
        "operator/Dockerfile"
        "operator/requirements.txt"
        "operator/README.md"
        "api/main.py"
        "api/auth.py"
        "api/models.py"
        "api/Dockerfile"
        "api/requirements.txt"
        "api/README.md"
        "crd/mcpservice.yaml"
        "chart/Chart.yaml"
        "chart/values.yaml"
        "chart/templates/_helpers.tpl"
        "chart/templates/rbac.yaml"
        "chart/templates/serviceaccount.yaml"
        "chart/templates/crd.yaml"
        "chart/templates/operator.yaml"
        "chart/templates/api.yaml"
        "chart/templates/ingress.yaml"
        "scripts/dev-setup.sh"
        "scripts/build-dev.sh"
        "scripts/uninstall.sh"
        "scripts/README.md"
        "examples/echo-mcp.yaml"
        "examples/calculator-mcp.yaml"
        "examples/file-tools-mcp.yaml"
        "examples/weather-mcp.yaml"
        "examples/README.md"
        "docs/QUICKSTART.md"
        "docs/ARCHITECTURE.md"
        "test/e2e-test.sh"
    )
    
    local missing_files=()
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -eq 0 ]]; then
        validation_result "Required Files Present" "PASS"
    else
        log_error "Missing files: ${missing_files[*]}"
        validation_result "Required Files Present" "FAIL"
    fi
}

# Directory structure validation
validate_directory_structure() {
    log_info "Validating directory structure..."
    
    local required_dirs=(
        "universal-adapter"
        "operator"
        "api"
        "crd"
        "chart"
        "chart/templates"
        "scripts"
        "examples"
        "docs"
        "test"
    )
    
    local missing_dirs=()
    
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            missing_dirs+=("$dir")
        fi
    done
    
    if [[ ${#missing_dirs[@]} -eq 0 ]]; then
        validation_result "Directory Structure" "PASS"
    else
        log_error "Missing directories: ${missing_dirs[*]}"
        validation_result "Directory Structure" "FAIL"
    fi
}

# Executable permissions
validate_executable_permissions() {
    log_info "Validating executable permissions..."
    
    local executable_files=(
        "install.sh"
        "scripts/dev-setup.sh"
        "scripts/build-dev.sh"
        "scripts/uninstall.sh"
        "test/e2e-test.sh"
    )
    
    local non_executable=()
    
    for file in "${executable_files[@]}"; do
        if [[ -f "$file" ]] && [[ ! -x "$file" ]]; then
            non_executable+=("$file")
        fi
    done
    
    if [[ ${#non_executable[@]} -eq 0 ]]; then
        validation_result "Executable Permissions" "PASS"
    else
        log_error "Non-executable files: ${non_executable[*]}"
        validation_result "Executable Permissions" "FAIL"
    fi
}

# Python syntax validation
validate_python_syntax() {
    log_info "Validating Python syntax..."
    
    local python_files=(
        "universal-adapter/main.py"
        "operator/main.py"
        "api/main.py"
        "api/auth.py"
        "api/models.py"
    )
    
    local syntax_errors=()
    
    for file in "${python_files[@]}"; do
        if [[ -f "$file" ]]; then
            if ! python3 -m py_compile "$file" &> /dev/null; then
                syntax_errors+=("$file")
            fi
        fi
    done
    
    if [[ ${#syntax_errors[@]} -eq 0 ]]; then
        validation_result "Python Syntax" "PASS"
    else
        log_error "Python syntax errors in: ${syntax_errors[*]}"
        validation_result "Python Syntax" "FAIL"
    fi
}

# YAML syntax validation
validate_yaml_syntax() {
    log_info "Validating YAML syntax..."
    
    local yaml_files=(
        "crd/mcpservice.yaml"
        "chart/Chart.yaml"
        "chart/values.yaml"
        "examples/echo-mcp.yaml"
        "examples/calculator-mcp.yaml"
        "examples/file-tools-mcp.yaml"
        "examples/weather-mcp.yaml"
    )
    
    local yaml_errors=()
    
    for file in "${yaml_files[@]}"; do
        if [[ -f "$file" ]]; then
            if command -v yq &> /dev/null; then
                if ! yq eval '.' "$file" &> /dev/null; then
                    yaml_errors+=("$file")
                fi
            elif command -v python3 &> /dev/null; then
                if ! python3 -c "import yaml; yaml.safe_load(open('$file'))" &> /dev/null; then
                    yaml_errors+=("$file")
                fi
            else
                log_warning "No YAML validator available (yq or python3+yaml)"
                validation_result "YAML Syntax (Skipped)" "PASS"
                return
            fi
        fi
    done
    
    if [[ ${#yaml_errors[@]} -eq 0 ]]; then
        validation_result "YAML Syntax" "PASS"
    else
        log_error "YAML syntax errors in: ${yaml_errors[*]}"
        validation_result "YAML Syntax" "FAIL"
    fi
}

# Dockerfile validation
validate_dockerfiles() {
    log_info "Validating Dockerfiles..."
    
    local dockerfiles=(
        "universal-adapter/Dockerfile"
        "operator/Dockerfile"
        "api/Dockerfile"
    )
    
    local dockerfile_errors=()
    
    for file in "${dockerfiles[@]}"; do
        if [[ -f "$file" ]]; then
            # Basic validation - check for required instructions
            if ! grep -q "FROM" "$file"; then
                dockerfile_errors+=("$file (missing FROM)")
            fi
            if ! grep -q "COPY\|ADD" "$file"; then
                dockerfile_errors+=("$file (missing COPY/ADD)")
            fi
            if ! grep -q "CMD\|ENTRYPOINT" "$file"; then
                dockerfile_errors+=("$file (missing CMD/ENTRYPOINT)")
            fi
        fi
    done
    
    if [[ ${#dockerfile_errors[@]} -eq 0 ]]; then
        validation_result "Dockerfile Structure" "PASS"
    else
        log_error "Dockerfile issues: ${dockerfile_errors[*]}"
        validation_result "Dockerfile Structure" "FAIL"
    fi
}

# Helm chart validation
validate_helm_chart() {
    log_info "Validating Helm chart..."
    
    if command -v helm &> /dev/null; then
        # Lint the chart
        if helm lint ./chart &> /dev/null; then
            validation_result "Helm Chart Lint" "PASS"
        else
            validation_result "Helm Chart Lint" "FAIL"
        fi
        
        # Template the chart
        if helm template test-release ./chart > /dev/null; then
            validation_result "Helm Chart Template" "PASS"
        else
            validation_result "Helm Chart Template" "FAIL"
        fi
    else
        log_warning "Helm not available - skipping chart validation"
        validation_result "Helm Chart Validation (Skipped)" "PASS"
    fi
}

# License validation
validate_license() {
    log_info "Validating license..."
    
    if [[ -f "LICENSE" ]]; then
        if grep -q "Apache License" LICENSE && grep -q "Version 2.0" LICENSE; then
            validation_result "Apache 2.0 License" "PASS"
        else
            validation_result "Apache 2.0 License" "FAIL"
        fi
    else
        validation_result "License File Exists" "FAIL"
    fi
}

# README validation
validate_readme() {
    log_info "Validating README..."
    
    if [[ -f "README.md" ]]; then
        local required_sections=(
            "# NimbleTools Core"
            "## Quick Start"
            "## Features"
            "## Installation"
            "## Architecture"
            "## Contributing"
            "## License"
        )
        
        local missing_sections=()
        
        for section in "${required_sections[@]}"; do
            if ! grep -q "$section" README.md; then
                missing_sections+=("$section")
            fi
        done
        
        if [[ ${#missing_sections[@]} -eq 0 ]]; then
            validation_result "README Sections" "PASS"
        else
            log_error "Missing README sections: ${missing_sections[*]}"
            validation_result "README Sections" "FAIL"
        fi
    else
        validation_result "README Exists" "FAIL"
    fi
}

# Version consistency validation
validate_version_consistency() {
    log_info "Validating version consistency..."
    
    local version_files=(
        "chart/Chart.yaml"
        "universal-adapter/__init__.py"
        "operator/__init__.py"
        "api/__init__.py"
    )
    
    local versions=()
    
    # Extract versions from different files
    if [[ -f "chart/Chart.yaml" ]]; then
        local chart_version=$(grep "^version:" chart/Chart.yaml | cut -d' ' -f2)
        versions+=("chart:$chart_version")
    fi
    
    if [[ -f "api/__init__.py" ]]; then
        local api_version=$(grep "__version__" api/__init__.py | cut -d'"' -f2)
        versions+=("api:$api_version")
    fi
    
    # Check if all versions are consistent
    local first_version=""
    local version_mismatch=false
    
    for version_info in "${versions[@]}"; do
        local version=$(echo "$version_info" | cut -d':' -f2)
        if [[ -z "$first_version" ]]; then
            first_version="$version"
        elif [[ "$version" != "$first_version" ]]; then
            version_mismatch=true
            break
        fi
    done
    
    if [[ "$version_mismatch" == "false" ]] && [[ -n "$first_version" ]]; then
        validation_result "Version Consistency ($first_version)" "PASS"
    else
        validation_result "Version Consistency" "FAIL"
    fi
}

# OSS domain validation
validate_oss_domain() {
    log_info "Validating OSS domain usage..."
    
    # Check that .dev domain is used instead of .ai
    local files_with_ai_domain=()
    
    # Search for .ai domain usage in key files
    local files_to_check=(
        "crd/mcpservice.yaml"
        "chart/values.yaml"
        "examples/*.yaml"
        "README.md"
    )
    
    for file_pattern in "${files_to_check[@]}"; do
        if compgen -G "$file_pattern" > /dev/null; then
            for file in $file_pattern; do
                if grep -q "nimbletools\.ai\|nimblebrain\.ai" "$file"; then
                    files_with_ai_domain+=("$file")
                fi
            done
        fi
    done
    
    if [[ ${#files_with_ai_domain[@]} -eq 0 ]]; then
        validation_result "OSS Domain Usage (.dev)" "PASS"
    else
        log_error "Files using .ai domain: ${files_with_ai_domain[*]}"
        validation_result "OSS Domain Usage (.dev)" "FAIL"
    fi
}

# Security validation
validate_security_practices() {
    log_info "Validating security practices..."
    
    local security_issues=()
    
    # Check for hardcoded secrets or API keys
    local files_to_scan=(
        "universal-adapter/main.py"
        "operator/main.py"
        "api/main.py"
        "api/auth.py"
        "examples/*.yaml"
    )
    
    for file_pattern in "${files_to_scan[@]}"; do
        if compgen -G "$file_pattern" > /dev/null; then
            for file in $file_pattern; do
                if grep -i "password\|secret\|key\|token" "$file" | grep -v "demo\|example\|placeholder"; then
                    # Check if these are actual hardcoded values (not just variable names)
                    if grep -E "(password|secret|key|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]" "$file" &> /dev/null; then
                        security_issues+=("Potential hardcoded secret in $file")
                    fi
                fi
            done
        fi
    done
    
    # Check Dockerfile security practices
    local dockerfiles=(
        "universal-adapter/Dockerfile"
        "operator/Dockerfile"
        "api/Dockerfile"
    )
    
    for dockerfile in "${dockerfiles[@]}"; do
        if [[ -f "$dockerfile" ]]; then
            if ! grep -q "USER " "$dockerfile"; then
                security_issues+=("$dockerfile missing USER instruction")
            fi
        fi
    done
    
    if [[ ${#security_issues[@]} -eq 0 ]]; then
        validation_result "Security Practices" "PASS"
    else
        log_error "Security issues: ${security_issues[*]}"
        validation_result "Security Practices" "FAIL"
    fi
}

# Main execution
main() {
    # Show banner
    cat << 'EOF'
    _   _ _           _     _     _____           _     
   | \ | (_)_ __ ___ | |__ | | __|_   _|__   ___ | |___ 
   |  \| | | '_ ` _ \| '_ \| |/ _ \| |/ _ \ / _ \| / __|
   | |\  | | | | | | | |_) | |  __/| | (_) | (_) | \__ \
   |_| \_|_|_| |_| |_|_.__/|_|\___||_|\___/ \___/|_|___/
                                                       
   Project Validation Suite
   
EOF
    
    log_info "Starting NimbleTools Core project validation..."
    
    # Run all validations
    validate_required_files
    validate_directory_structure
    validate_executable_permissions
    validate_python_syntax
    validate_yaml_syntax
    validate_dockerfiles
    validate_helm_chart
    validate_license
    validate_readme
    validate_version_consistency
    validate_oss_domain
    validate_security_practices
    
    # Show results
    echo ""
    log_info "==============================================="
    log_info "Project Validation Results"
    log_info "==============================================="
    log_info "Total Validations: $((VALIDATIONS_PASSED + VALIDATIONS_FAILED))"
    log_success "Passed: $VALIDATIONS_PASSED"
    
    if [[ $VALIDATIONS_FAILED -gt 0 ]]; then
        log_error "Failed: $VALIDATIONS_FAILED"
        log_error "Failed Validations:"
        for validation in "${FAILED_VALIDATIONS[@]}"; do
            log_error "  - $validation"
        done
    fi
    
    log_info "==============================================="
    
    # Exit with appropriate code
    if [[ $VALIDATIONS_FAILED -gt 0 ]]; then
        log_error "Project validation failed. Please fix the issues above."
        exit 1
    else
        log_success "All validations passed! Project is ready for release. 🎉"
        exit 0
    fi
}

# Run main function
main "$@"