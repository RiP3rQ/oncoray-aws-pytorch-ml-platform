{{- define "platform-addons.name" -}}
{{- default .Chart.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "platform-addons.fullname" -}}
{{- printf "%s-%s" .Release.Name (include "platform-addons.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "platform-addons.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
app.kubernetes.io/name: {{ include "platform-addons.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.global.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}
