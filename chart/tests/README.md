# Helm Chart Unit Tests

This directory contains unit tests for the NimbleTools Core Helm chart using the [helm-unittest](https://github.com/helm-unittest/helm-unittest) plugin.

## Overview

Helm chart unit tests verify that templates render correctly with different configurations. These tests run without a Kubernetes cluster and are fast enough to run in CI/CD pipelines.

## Test Philosophy

Similar to Python unit tests (TDD):

1. **Arrange**: Set up input values
2. **Act**: Render the template (done by helm-unittest)
3. **Assert**: Verify the output YAML structure

## Prerequisites

Install the helm-unittest plugin:

```bash
helm plugin install https://github.com/helm-unittest/helm-unittest
```

Verify installation:

```bash
helm unittest --help
```

## Running Tests

### Run all tests

From the repository root:

```bash
helm unittest chart/
```

Or from the chart directory:

```bash
cd chart
helm unittest .
```

### Run specific test suite

```bash
helm unittest -f 'tests/control_plane_extraenv_test.yaml' chart/
```

### Run with verbose output

```bash
helm unittest -v chart/
```

### Run with coverage report

```bash
helm unittest --with-subchart=false chart/
```

## Test Structure

### Test Files

- `control_plane_extraenv_test.yaml` - Tests for control-plane extraEnv functionality
- `operator_extraenv_test.yaml` - Tests for operator extraEnv functionality
- `rbac_controller_extraenv_test.yaml` - Tests for rbac-controller extraEnv functionality

### Test Anatomy

```yaml
suite: test description
templates:
  - template_name.yaml
tests:
  - it: should do something specific
    values:
      - ../values.yaml  # Base values
    set:
      # Override specific values for this test
      extraEnv:
        - name: TEST_VAR
          value: "test"
    asserts:
      - contains:
          path: spec.template.spec.containers[0].env
          content:
            name: TEST_VAR
            value: "test"
```

## What We Test

### Backward Compatibility

Ensure existing configurations continue to work:

```yaml
- it: should support simple value in extraEnv
  set:
    extraEnv:
      - name: EDITION
        value: "enterprise"
  asserts:
    - contains:
        path: spec.template.spec.containers[0].env
        content:
          name: EDITION
          value: "enterprise"
```

### New Features

Verify new valueFrom functionality:

```yaml
- it: should support secretKeyRef in extraEnv
  set:
    extraEnv:
      - name: API_KEY
        valueFrom:
          secretKeyRef:
            name: api-credentials
            key: api-key
  asserts:
    - contains:
        path: spec.template.spec.containers[0].env
        content:
          name: API_KEY
          valueFrom:
            secretKeyRef:
              name: api-credentials
              key: api-key
```

### Edge Cases

Test mixed configurations and edge cases:

```yaml
- it: should support mixed value and valueFrom
  set:
    extraEnv:
      - name: SIMPLE
        value: "simple"
      - name: SECRET
        valueFrom:
          secretKeyRef:
            name: secret-name
            key: key-name
  asserts:
    # ... assertions for both types
```

## Common Assertions

### Check value exists

```yaml
- isNotNull:
    path: spec.template.spec.containers[0].env
```

### Check specific value

```yaml
- equal:
    path: spec.template.spec.containers[0].name
    value: control-plane
```

### Check array contains

```yaml
- contains:
    path: spec.template.spec.containers[0].env
    content:
      name: MY_VAR
      value: "my-value"
```

### Check resource kind

```yaml
- isKind:
    of: Deployment
```

### Check value is not present

```yaml
- notContains:
    path: spec.template.spec.containers[0].env
    content:
      name: SHOULD_NOT_EXIST
```

## Integration with CI/CD

### GitHub Actions Example

Add to `.github/workflows/test.yml`:

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

      - name: Install helm-unittest plugin
        run: helm plugin install https://github.com/helm-unittest/helm-unittest

      - name: Run helm unit tests
        run: helm unittest chart/

      - name: Run helm lint
        run: helm lint chart/
```

### Makefile Integration

Add to repository Makefile:

```makefile
.PHONY: test-chart
test-chart:
	@echo "Running Helm chart unit tests..."
	helm unittest chart/

.PHONY: test-chart-verbose
test-chart-verbose:
	@echo "Running Helm chart unit tests (verbose)..."
	helm unittest -v chart/

.PHONY: lint-chart
lint-chart:
	@echo "Linting Helm chart..."
	helm lint chart/
```

## Writing New Tests

### 1. Create test file

Create a new file in `chart/tests/` following the naming convention:
`<component>_<feature>_test.yaml`

### 2. Define test suite

```yaml
suite: test description
templates:
  - your_template.yaml
tests:
  - it: should test something
    # ... test definition
```

### 3. Run tests locally

```bash
helm unittest chart/
```

### 4. Verify coverage

Ensure you test:
- Default values (backward compatibility)
- New functionality
- Edge cases (empty values, mixed configs)
- Error conditions (if applicable)

## Best Practices

1. **One assertion per test**: Each test should verify one specific behavior
2. **Descriptive names**: Use clear "should do X when Y" naming
3. **Test backward compatibility**: Always verify existing configs still work
4. **Cover edge cases**: Empty lists, null values, mixed configurations
5. **Keep tests independent**: Each test should be runnable in isolation
6. **Use realistic values**: Test with values users would actually use

## Debugging Failed Tests

### View rendered template

```bash
helm template test-release chart/ -f chart/tests/test-values.yaml
```

### Check specific path

```bash
helm template test-release chart/ \
  --set extraEnv[0].name=TEST \
  --set extraEnv[0].value=value | \
  yq '.spec.template.spec.containers[0].env'
```

### Run single test

```bash
helm unittest -f 'tests/control_plane_extraenv_test.yaml' chart/
```

## Related Testing Approaches

### Helm Lint

Basic syntax and best practices check:

```bash
helm lint chart/
```

### Helm Template Validation

Render and validate against Kubernetes schemas:

```bash
helm template test-release chart/ | kubectl apply --dry-run=client -f -
```

### Integration Tests

For full end-to-end testing, see:
- `scripts/test-deploy.sh` - Deploy to test cluster
- `scripts/integration-tests.sh` - Run integration tests

## Resources

- [helm-unittest documentation](https://github.com/helm-unittest/helm-unittest)
- [Helm best practices](https://helm.sh/docs/chart_best_practices/)
- [Testing Helm Charts](https://helm.sh/docs/topics/chart_tests/)
