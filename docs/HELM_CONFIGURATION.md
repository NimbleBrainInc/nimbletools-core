# Helm Chart Configuration Guide

This document provides detailed information about configuring the NimbleTools Core Helm chart.

## Table of Contents

- [Overview](#overview)
- [Basic Configuration](#basic-configuration)
- [Environment Variables (extraEnv)](#environment-variables-extraenv)
- [Component Configuration](#component-configuration)
- [Security Configuration](#security-configuration)
- [Resource Management](#resource-management)
- [Networking](#networking)

## Overview

The NimbleTools Core Helm chart deploys a complete MCP platform with the following components:

- **Control Plane**: REST API for managing workspaces and servers
- **Operator**: Kubernetes operator managing MCPService lifecycle
- **RBAC Controller**: Manages workspace-level access control
- **Universal Adapter**: Wraps stdio servers for HTTP transport

## Basic Configuration

### Minimal Installation

```yaml
global:
  domain: nimbletools.dev
```

### Custom Registry

```yaml
global:
  imageRegistry: my-registry.example.com
  imagePullSecrets:
    - name: registry-credentials
```

## Environment Variables (extraEnv)

The `extraEnv` configuration applies to all components (control-plane, operator, rbac-controller) and supports both simple values and Kubernetes' `valueFrom` syntax for dynamic value sources.

### Simple Values

Basic environment variables with static values:

```yaml
extraEnv:
  - name: EDITION
    value: "enterprise"
  - name: LOG_LEVEL
    value: "debug"
  - name: FEATURE_FLAG
    value: "enabled"
```

### Secret References

Reference values from Kubernetes secrets:

```yaml
extraEnv:
  - name: API_KEY
    valueFrom:
      secretKeyRef:
        name: api-credentials
        key: api-key

  - name: DATABASE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: password
        optional: true  # Won't fail if secret doesn't exist
```

**Prerequisites**: Create the secret before deployment:

```bash
kubectl create secret generic api-credentials \
  --from-literal=api-key=your-secret-key
```

### ConfigMap References

Reference values from ConfigMaps:

```yaml
extraEnv:
  - name: APP_CONFIG
    valueFrom:
      configMapKeyRef:
        name: app-config
        key: config-value

  - name: ENVIRONMENT
    valueFrom:
      configMapKeyRef:
        name: deployment-config
        key: environment
```

**Prerequisites**: Create the ConfigMap:

```bash
kubectl create configmap app-config \
  --from-literal=config-value=production
```

### Field References

Reference pod or container metadata:

```yaml
extraEnv:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name

  - name: POD_NAMESPACE
    valueFrom:
      fieldRef:
        fieldPath: metadata.namespace

  - name: POD_IP
    valueFrom:
      fieldRef:
        fieldPath: status.podIP

  - name: NODE_NAME
    valueFrom:
      fieldRef:
        fieldPath: spec.nodeName
```

### Resource Field References

Reference container resource limits and requests:

```yaml
extraEnv:
  - name: MEMORY_LIMIT
    valueFrom:
      resourceFieldRef:
        containerName: control-plane
        resource: limits.memory

  - name: CPU_REQUEST
    valueFrom:
      resourceFieldRef:
        containerName: operator
        resource: requests.cpu
```

### Mixed Configuration

Combine multiple value sources:

```yaml
extraEnv:
  # Simple values
  - name: EDITION
    value: "enterprise"

  # Secret references
  - name: AUTH_SECRET
    valueFrom:
      secretKeyRef:
        name: auth-secret
        key: secret-key

  # ConfigMap references
  - name: REGION
    valueFrom:
      configMapKeyRef:
        name: deployment-config
        key: region

  # Field references
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name

  # More simple values
  - name: DEBUG
    value: "true"
```

### Enterprise Authentication Example

Configure enterprise authentication provider with secrets:

```yaml
extraEnv:
  # Static configuration
  - name: PROVIDER_TYPE
    value: "jwt"

  # Secret references for sensitive data
  - name: JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: jwt-config
        key: secret

  - name: JWT_ISSUER
    valueFrom:
      secretKeyRef:
        name: jwt-config
        key: issuer

  # Optional OAuth configuration
  - name: OAUTH_CLIENT_SECRET
    valueFrom:
      secretKeyRef:
        name: oauth-credentials
        key: client-secret
        optional: true
```

### External Secret Management Integration

Integration with external secret managers (Vault, 1Password, AWS Secrets Manager, etc.):

```yaml
extraEnv:
  # Reference secrets created by external secret operators
  - name: DATABASE_URI
    valueFrom:
      secretKeyRef:
        name: postgres-creds  # Created by External Secrets Operator
        key: connection-uri

  - name: API_TOKEN
    valueFrom:
      secretKeyRef:
        name: vault-api-tokens  # Created by Vault injector
        key: nimbletools-token
```

## Component Configuration

### Control Plane

```yaml
controlPlane:
  enabled: true
  replicas: 2

  image:
    repository: nimbletools/control-plane
    tag: "0.2.1"
    pullPolicy: IfNotPresent

  service:
    type: ClusterIP
    port: 8080

  resources:
    limits:
      cpu: "500m"
      memory: "512Mi"
    requests:
      cpu: "100m"
      memory: "128Mi"

  cors:
    allowOrigins: ["*"]
    allowMethods: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    allowHeaders: ["*"]
```

### Operator

```yaml
operator:
  replicas: 1

  image:
    repository: nimbletools/mcp-operator
    tag: "0.2.1"

  config:
    logLevel: "info"
    reconcileInterval: "30s"
    enableMetrics: true
    metricsPort: 8080

  resources:
    limits:
      cpu: "1000m"
      memory: "1Gi"
    requests:
      cpu: "200m"
      memory: "256Mi"
```

### RBAC Controller

```yaml
rbacController:
  enabled: true
  replicas: 1

  image:
    repository: nimbletools/rbac-controller
    tag: "0.2.1"

  resources:
    limits:
      cpu: "100m"
      memory: "128Mi"
    requests:
      cpu: "50m"
      memory: "64Mi"
```

## Security Configuration

### Pod Security Context

```yaml
podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  fsGroup: 1000

securityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
```

### RBAC Configuration

```yaml
rbac:
  create: true

serviceAccount:
  create: true
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/nimbletools-role
```

## Resource Management

### Default MCP Service Resources

```yaml
universalAdapter:
  resources:
    limits:
      cpu: "500m"
      memory: "512Mi"
    requests:
      cpu: "100m"
      memory: "128Mi"
```

### Node Selection

```yaml
nodeSelector:
  workload-type: mcp-services

tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "mcp"
    effect: "NoSchedule"

affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values: ["control-plane"]
          topologyKey: kubernetes.io/hostname
```

## Networking

### Ingress Configuration

```yaml
ingress:
  enabled: true
  className: "nginx"

  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"

  tls:
    - hosts:
        - api.nimbletools.example.com
      secretName: nimbletools-tls

  api:
    paths:
      - path: /
        pathType: Prefix
```

### Custom Domain

```yaml
global:
  domain: api.company.com
```

## Advanced Configuration

### Additional Volumes

```yaml
extraVolumes:
  - name: config-volume
    configMap:
      name: app-config

  - name: secret-volume
    secret:
      secretName: app-secrets

  - name: cache-volume
    emptyDir:
      sizeLimit: 1Gi

extraVolumeMounts:
  - name: config-volume
    mountPath: /etc/config
    readOnly: true

  - name: secret-volume
    mountPath: /etc/secrets
    readOnly: true

  - name: cache-volume
    mountPath: /tmp/cache
```

### Monitoring

```yaml
monitoring:
  enabled: true

operator:
  config:
    enableMetrics: true
    metricsPort: 8080
```

## Complete Example

Full production configuration example:

```yaml
global:
  domain: api.nimbletools.company.com
  imageRegistry: company-registry.example.com
  namespace: nimbletools-production

# Environment variables for all components
extraEnv:
  # Static configuration
  - name: EDITION
    value: "enterprise"
  - name: ENVIRONMENT
    value: "production"

  # Secret references
  - name: JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: auth-secrets
        key: jwt-secret

  - name: DATABASE_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgres-creds
        key: password

  # Pod metadata
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name

controlPlane:
  replicas: 3
  resources:
    limits:
      cpu: "1000m"
      memory: "1Gi"
    requests:
      cpu: "200m"
      memory: "256Mi"

operator:
  replicas: 2
  config:
    logLevel: "info"
    enableMetrics: true

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  tls:
    - hosts:
        - api.nimbletools.company.com
      secretName: nimbletools-tls

monitoring:
  enabled: true

podSecurityContext:
  runAsNonRoot: true
  runAsUser: 1000
  fsGroup: 1000
```

## Troubleshooting

### Verify Environment Variables

Check that environment variables are correctly applied:

```bash
# Control plane
kubectl get deployment nimbletools-core-control-plane -o jsonpath='{.spec.template.spec.containers[0].env}' | jq

# Operator
kubectl get deployment nimbletools-core-operator -o jsonpath='{.spec.template.spec.containers[0].env}' | jq

# RBAC controller
kubectl get deployment nimbletools-core-rbac-controller -o jsonpath='{.spec.template.spec.containers[0].env}' | jq
```

### Check Secret References

Verify secrets exist and are accessible:

```bash
kubectl get secret api-credentials -o yaml
kubectl describe secret api-credentials
```

### Template Debugging

Render templates locally to verify configuration:

```bash
helm template nimbletools ./chart -f my-values.yaml --debug
```
