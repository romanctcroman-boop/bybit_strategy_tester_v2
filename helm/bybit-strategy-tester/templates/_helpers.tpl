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
app.kubernetes.io/part-of: bybit-strategy-tester
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
{{- if .Values.serviceAccount.create }}
{{- default (include "bybit-strategy-tester.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Database URL helper
*/}}
{{- define "bybit-strategy-tester.databaseUrl" -}}
postgresql://$(DB_USER):$(DB_PASS)@{{ .Values.config.DB_HOST }}:{{ .Values.config.DB_PORT }}/{{ .Values.config.DB_NAME }}
{{- end }}

{{/*
Redis URL helper
*/}}
{{- define "bybit-strategy-tester.redisUrl" -}}
redis://:$(REDIS_PASSWORD)@{{ .Values.config.REDIS_HOST }}:{{ .Values.config.REDIS_PORT }}/0
{{- end }}

{{/*
Celery Broker URL helper
*/}}
{{- define "bybit-strategy-tester.celeryBrokerUrl" -}}
redis://:$(REDIS_PASSWORD)@{{ .Values.config.REDIS_HOST }}:{{ .Values.config.REDIS_PORT }}/1
{{- end }}

{{/*
Celery Result Backend URL helper
*/}}
{{- define "bybit-strategy-tester.celeryResultUrl" -}}
redis://:$(REDIS_PASSWORD)@{{ .Values.config.REDIS_HOST }}:{{ .Values.config.REDIS_PORT }}/2
{{- end }}
