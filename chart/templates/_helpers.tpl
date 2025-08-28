{{/*
Expand the name of the chart.
*/}}
{{- define "nimbletools-core.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "nimbletools-core.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "nimbletools-core.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "nimbletools-core.labels" -}}
helm.sh/chart: {{ include "nimbletools-core.chart" . }}
{{ include "nimbletools-core.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "nimbletools-core.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nimbletools-core.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "nimbletools-core.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "nimbletools-core.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Create the name of the operator
*/}}
{{- define "nimbletools-core.operatorName" -}}
{{- printf "%s-operator" (include "nimbletools-core.fullname" .) }}
{{- end }}

{{/*
Create the name of the Control Plane server
*/}}
{{- define "nimbletools-core.controlPlaneName" -}}
{{- printf "%s-control-plane" (include "nimbletools-core.fullname" .) }}
{{- end }}

{{/*
Operator labels
*/}}
{{- define "nimbletools-core.operatorLabels" -}}
{{ include "nimbletools-core.labels" . }}
app.kubernetes.io/component: operator
{{- end }}

{{/*
Control Plane labels
*/}}
{{- define "nimbletools-core.controlPlaneLabels" -}}
{{ include "nimbletools-core.labels" . }}
app.kubernetes.io/component: control-plane
{{- end }}

{{/*
Operator selector labels
*/}}
{{- define "nimbletools-core.operatorSelectorLabels" -}}
{{ include "nimbletools-core.selectorLabels" . }}
app.kubernetes.io/component: operator
{{- end }}

{{/*
Control Plane selector labels
*/}}
{{- define "nimbletools-core.controlPlaneSelectorLabels" -}}
{{ include "nimbletools-core.selectorLabels" . }}
app.kubernetes.io/component: control-plane
{{- end }}

{{/*
Create the name of the RBAC controller
*/}}
{{- define "nimbletools-core.rbacControllerName" -}}
{{- printf "%s-rbac-controller" (include "nimbletools-core.fullname" .) }}
{{- end }}

{{/*
RBAC Controller labels
*/}}
{{- define "nimbletools-core.rbacControllerLabels" -}}
{{ include "nimbletools-core.labels" . }}
app.kubernetes.io/component: rbac-controller
{{- end }}

{{/*
RBAC Controller selector labels
*/}}
{{- define "nimbletools-core.rbacControllerSelectorLabels" -}}
{{ include "nimbletools-core.selectorLabels" . }}
app.kubernetes.io/component: rbac-controller
{{- end }}