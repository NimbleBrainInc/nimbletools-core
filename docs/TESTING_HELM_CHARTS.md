# Testing Helm Charts: A Complete Guide

This document explains how we test Kubernetes/Helm changes using the same TDD principles as Python unit tests.

## Philosophy: TDD for Helm Charts

Just like Python unit tests, Helm chart tests follow the Arrange-Act-Assert pattern:

1. **Arrange**: Set up input values (like Python test fixtures)
2. **Act**: Render the template (done automatically by helm-unittest)
3. **Assert**: Verify the output YAML structure (like Python assertions)

## Tools We Use

### helm-unittest Plugin

The industry-standard tool for unit testing Helm charts:
- Fast execution (no Kubernetes cluster required)
- Runs in CI/CD pipelines
- Tests template logic without deployment
- Works like pytest for Helm templates

**Installation:**
```bash
helm plugin install https://github.com/helm-unittest/helm-unittest
```

## Test Structure

### Directory Layout

```
chart/
├── templates/
│   ├── control_plane.yaml
│   ├── operator.yaml
│   └── rbac-controller.yaml
└── tests/
    ├── control_plane_extraenv_test.yaml
    ├── operator_extraenv_test.yaml
    └── rbac_controller_extraenv_test.yaml
```

### Anatomy of a Test

```yaml
suite: test description
templates:
  - control_plane.yaml
tests:
  - it: should support secretKeyRef in extraEnv
    values:
      - ../values.yaml          # Base values (like fixture)
    documentIndex: 0            # Which K8s resource in the template
    set:                        # Override values for this test
      extraEnv:
        - name: API_KEY
          valueFrom:
            secretKeyRef:
              name: api-credentials
              key: api-key
    asserts:                    # Verify the rendered output
      - contains:
          path: spec.template.spec.containers[0].env
          content:
            name: API_KEY
            valueFrom:
              secretKeyRef:
                name: api-credentials
                key: api-key
```

## Key Concepts

### Document Index

Helm templates can output multiple Kubernetes resources. Use `documentIndex` to target the right one:

```yaml
# control_plane.yaml outputs:
# - Document 0: Deployment
# - Document 1: Service

documentIndex: 0  # Test the Deployment
```

### Common Assertions

**Check value exists:**
```yaml
- isNotNull:
    path: spec.template.spec.containers[0].env
```

**Check specific value:**
```yaml
- equal:
    path: spec.template.spec.containers[0].name
    value: control-plane
```

**Check array contains:**
```yaml
- contains:
    path: spec.template.spec.containers[0].env
    content:
      name: MY_VAR
      value: "my-value"
```

**Check resource kind:**
```yaml
- isKind:
    of: Deployment
```

## Running Tests

### Quick Commands

```bash
# Run all tests
make test-chart

# Verbose output
make test-chart-verbose

# Run specific test file
helm unittest -f 'tests/control_plane_extraenv_test.yaml' chart/

# Just lint (no tests)
make lint-chart
```

### Full Test Script

```bash
./scripts/test-chart.sh
```

This script runs:
1. Helm lint (checks best practices)
2. Unit tests (verifies template logic)
3. Template rendering validation

## Test Coverage for extraEnv Fix

Our extraEnv fix includes comprehensive tests covering:

### Backward Compatibility Tests

**Test:** Existing simple values still work
```yaml
- it: should support simple value in extraEnv
  set:
    extraEnv:
      - name: EDITION
        value: "enterprise"
```

**Why:** Ensures no breaking changes for current users

### New Feature Tests

**Test:** Secret references work
```yaml
- it: should support secretKeyRef in extraEnv
  set:
    extraEnv:
      - name: API_KEY
        valueFrom:
          secretKeyRef:
            name: api-credentials
            key: api-key
```

**Why:** Verifies the new valueFrom functionality

### Edge Case Tests

**Test:** Mixed value and valueFrom
```yaml
- it: should support mixed value and valueFrom
  set:
    extraEnv:
      - name: SIMPLE
        value: "value"
      - name: SECRET
        valueFrom:
          secretKeyRef:
            name: secret
            key: key
```

**Why:** Tests real-world usage patterns

### All Value Sources

**Tests include:**
- `secretKeyRef` - Kubernetes secrets
- `configMapKeyRef` - ConfigMaps
- `fieldRef` - Pod metadata
- `resourceFieldRef` - Container resources
- `optional: true` - Optional secrets

## Comparison to Python Unit Tests

| Python Tests | Helm Tests |
|-------------|-----------|
| `pytest` | `helm unittest` |
| `@pytest.fixture` | `values:` section |
| Function under test | Template rendering |
| `assert x == y` | `asserts:` section |
| `mock.patch()` | `set:` overrides |
| Test file: `test_*.py` | Test file: `*_test.yaml` |
| `pytest -v` | `helm unittest -v` |

## Integration with CI/CD

### GitHub Actions

```yaml
name: Test Helm Chart
on: [push, pull_request]

jobs:
  helm-unittest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Helm
        uses: azure/setup-helm@v3
        with:
          version: '3.13.0'

      - name: Install helm-unittest
        run: helm plugin install https://github.com/helm-unittest/helm-unittest

      - name: Run tests
        run: helm unittest chart/
```

### Make Integration

```makefile
verify-chart: ## Run Helm chart unit tests
	@./scripts/test-chart.sh

test-chart-verbose: ## Verbose output
	@./scripts/test-chart.sh -v

lint-chart: ## Lint only
	@helm lint chart/
```

## Best Practices

### 1. One Assertion Per Test

✅ **Good:**
```yaml
- it: should set container name
  asserts:
    - equal:
        path: spec.template.spec.containers[0].name
        value: control-plane
```

❌ **Bad:**
```yaml
- it: should configure everything
  asserts:
    - equal: {path: spec.template.spec.containers[0].name, value: control-plane}
    - equal: {path: spec.replicas, value: 2}
    - contains: {path: spec.template.spec.containers[0].env, ...}
    # Too many unrelated assertions
```

### 2. Descriptive Test Names

Use "should do X when Y" format:
```yaml
- it: should support secretKeyRef when valueFrom is set
- it: should maintain backward compatibility with simple values
- it: should handle empty extraEnv list
```

### 3. Test Backward Compatibility

Always verify existing configurations still work:
```yaml
- it: should handle default empty extraEnv
  values:
    - ../values.yaml  # Default values
  asserts:
    - isKind:
        of: Deployment
```

### 4. Cover Edge Cases

```yaml
- it: should support optional secrets
- it: should handle mixed value and valueFrom
- it: should work when extraEnv is empty
```

### 5. Use Realistic Values

Test with values users would actually use:
```yaml
set:
  extraEnv:
    - name: JWT_SECRET
      valueFrom:
        secretKeyRef:
          name: auth-secrets
          key: jwt-secret
    - name: ENVIRONMENT
      value: "production"
```

## Debugging Failed Tests

### View Rendered Template

```bash
helm template test-release chart/ -f chart/tests/test-values.yaml
```

### Check Specific Path

```bash
helm template test-release chart/ \
  --set extraEnv[0].name=TEST \
  --set extraEnv[0].value=value | \
  yq '.spec.template.spec.containers[0].env'
```

### Run Single Test

```bash
helm unittest -f 'tests/control_plane_extraenv_test.yaml' chart/
```

### Verbose Output

```bash
helm unittest -v chart/
```

## Testing Pyramid

Our testing strategy follows the testing pyramid:

```
        /\
       /  \      E2E Tests (integration-tests.sh)
      /____\     - Full deployment to k3d cluster
     /      \    - Real Kubernetes validation
    /        \   - Slower, fewer tests
   /          \
  /__Unit____\ Unit Tests (helm unittest)
                - Template logic verification
                - Fast, many tests
                - No cluster required
```

### Unit Tests (helm-unittest)

**When:** On every commit
**Speed:** ~50ms
**Coverage:** Template logic, value interpolation, conditionals
**No cluster required**

### Integration Tests (test-deploy.sh)

**When:** Before merge/release
**Speed:** ~2 minutes
**Coverage:** Actual deployment, pod startup, service connectivity
**Requires k3d cluster**

### E2E Tests (manual/automated)

**When:** Before production release
**Speed:** ~10 minutes
**Coverage:** Full workflows, API calls, MCP server deployment
**Requires full platform**

## Real-World Example: extraEnv valueFrom Fix

### The Problem

Users couldn't reference Kubernetes secrets in extraEnv:

```yaml
extraEnv:
  - name: API_KEY
    valueFrom:  # This was ignored!
      secretKeyRef:
        name: api-credentials
        key: api-key
```

### The Solution

Updated template to support both `value` and `valueFrom`:

```yaml
{{- range .Values.extraEnv }}
- name: {{ .name }}
  {{- if .value }}
  value: {{ .value | quote }}
  {{- else if .valueFrom }}
  valueFrom:
    {{- toYaml .valueFrom | nindent 12 }}
  {{- end }}
{{- end }}
```

### The Tests

**18 tests covering:**
- 3 components (control-plane, operator, rbac-controller)
- Backward compatibility (simple values)
- New functionality (all valueFrom types)
- Edge cases (mixed configs, optional secrets)

**Result:** All tests pass in ~50ms

## Further Reading

- [helm-unittest documentation](https://github.com/helm-unittest/helm-unittest)
- [Helm best practices](https://helm.sh/docs/chart_best_practices/)
- [Testing Helm Charts (official)](https://helm.sh/docs/topics/chart_tests/)
- [Project test files](../chart/tests/)
- [Test runner script](../scripts/test-chart.sh)
