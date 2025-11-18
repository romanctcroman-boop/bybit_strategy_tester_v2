{{/*
Expand the name of the chart.
*/}}
{{- define "bybit-strategy-tester.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "bybit-strategy-tester.fullname" -}}
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
{{- define "bybit-strategy-tester.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "bybit-strategy-tester.labels" -}}
helm.sh/chart: {{ include "bybit-strategy-tester.chart" . }}
{{ include "bybit-strategy-tester.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
environment: {{ .Values.global.environment }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "bybit-strategy-tester.selectorLabels" -}}
app.kubernetes.io/name: {{ include "bybit-strategy-tester.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "bybit-strategy-tester.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create }}
{{- default (include "bybit-strategy-tester.fullname" .) .Values.security.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.security.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Backend labels
*/}}
{{- define "backend.labels" -}}
{{ include "bybit-strategy-tester.labels" . }}
app: backend
component: api
tier: backend
{{- end }}

{{/*
Backend selector labels
*/}}
{{- define "backend.selectorLabels" -}}
{{ include "bybit-strategy-tester.selectorLabels" . }}
app: backend
{{- end }}

{{/*
Worker labels
*/}}
{{- define "worker.labels" -}}
{{ include "bybit-strategy-tester.labels" . }}
app: worker
component: executor
tier: backend
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "worker.selectorLabels" -}}
{{ include "bybit-strategy-tester.selectorLabels" . }}
app: worker
{{- end }}

{{/*
Redis labels
*/}}
{{- define "redis.labels" -}}
{{ include "bybit-strategy-tester.labels" . }}
app: redis
component: cache
tier: data
{{- end }}

{{/*
PostgreSQL labels
*/}}
{{- define "postgresql.labels" -}}
{{ include "bybit-strategy-tester.labels" . }}
app: postgresql
component: database
tier: data
{{- end }}
