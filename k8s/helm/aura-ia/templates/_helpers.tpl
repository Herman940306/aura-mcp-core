{{/*
Expand the name of the chart.
*/}}
{{- define "aura-ia.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "aura-ia.fullname" -}}
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
{{- define "aura-ia.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "aura-ia.labels" -}}
helm.sh/chart: {{ include "aura-ia.chart" . }}
{{ include "aura-ia.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "aura-ia.selectorLabels" -}}
app.kubernetes.io/name: {{ include "aura-ia.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "aura-ia.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "aura-ia.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Gateway labels
*/}}
{{- define "aura-ia.gateway.labels" -}}
{{ include "aura-ia.labels" . }}
app.kubernetes.io/component: gateway
{{- end }}

{{- define "aura-ia.gateway.selectorLabels" -}}
{{ include "aura-ia.selectorLabels" . }}
app.kubernetes.io/component: gateway
{{- end }}

{{/*
ML Backend labels
*/}}
{{- define "aura-ia.ml.labels" -}}
{{ include "aura-ia.labels" . }}
app.kubernetes.io/component: ml-backend
{{- end }}

{{- define "aura-ia.ml.selectorLabels" -}}
{{ include "aura-ia.selectorLabels" . }}
app.kubernetes.io/component: ml-backend
{{- end }}

{{/*
RAG labels
*/}}
{{- define "aura-ia.rag.labels" -}}
{{ include "aura-ia.labels" . }}
app.kubernetes.io/component: rag
{{- end }}

{{- define "aura-ia.rag.selectorLabels" -}}
{{ include "aura-ia.selectorLabels" . }}
app.kubernetes.io/component: rag
{{- end }}

{{/*
Dashboard labels
*/}}
{{- define "aura-ia.dashboard.labels" -}}
{{ include "aura-ia.labels" . }}
app.kubernetes.io/component: dashboard
{{- end }}

{{- define "aura-ia.dashboard.selectorLabels" -}}
{{ include "aura-ia.selectorLabels" . }}
app.kubernetes.io/component: dashboard
{{- end }}
