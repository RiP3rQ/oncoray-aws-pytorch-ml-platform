{{- define "backend-stack.name" -}}
{{- default .Chart.Name .Values.global.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "backend-stack.fullname" -}}
{{- if .Values.global.fullnameOverride -}}
{{- .Values.global.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "backend-stack.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "backend-stack.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "backend-stack.labels" -}}
helm.sh/chart: {{ include "backend-stack.chart" . }}
app.kubernetes.io/name: {{ include "backend-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "backend-stack.selectorLabels" -}}
app.kubernetes.io/name: {{ include "backend-stack.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "backend-stack.componentName" -}}
{{- printf "%s-%s" (include "backend-stack.fullname" .root) .component | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "backend-stack.serviceAccountName" -}}
{{- $root := .root -}}
{{- $workload := .workload -}}
{{- if $workload.serviceAccount.create -}}
{{- default (include "backend-stack.componentName" (dict "root" $root "component" .component)) $workload.serviceAccount.name -}}
{{- else -}}
{{- default "default" $workload.serviceAccount.name -}}
{{- end -}}
{{- end -}}
