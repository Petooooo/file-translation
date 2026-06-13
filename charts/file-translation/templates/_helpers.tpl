{{/*
Expand the name of the chart.
*/}}
{{- define "file-translation.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "file-translation.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "file-translation.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" -}}
{{- end -}}

{{- define "file-translation.labels" -}}
helm.sh/chart: {{ include "file-translation.chart" . }}
app.kubernetes.io/name: {{ include "file-translation.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: file-translation
{{- with .Values.global.labels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{- define "file-translation.selectorLabels" -}}
app.kubernetes.io/name: {{ include "file-translation.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/part-of: file-translation
{{- end -}}

{{- define "file-translation.configName" -}}
{{- printf "%s-config" (include "file-translation.fullname" .) -}}
{{- end -}}

{{- define "file-translation.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "file-translation.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "file-translation.jobServiceName" -}}
{{- printf "%s-job-service" (include "file-translation.fullname" .) -}}
{{- end -}}

{{- define "file-translation.rabbitmqName" -}}
{{- printf "%s-rabbitmq" (include "file-translation.fullname" .) -}}
{{- end -}}

{{- define "file-translation.postgresqlName" -}}
{{- printf "%s-postgresql" (include "file-translation.fullname" .) -}}
{{- end -}}

{{- define "file-translation.minioName" -}}
{{- printf "%s-minio" (include "file-translation.fullname" .) -}}
{{- end -}}

{{- define "file-translation.rabbitmqHost" -}}
{{- if .Values.rabbitmq.external -}}
{{- .Values.rabbitmq.host -}}
{{- else -}}
{{- include "file-translation.rabbitmqName" . -}}
{{- end -}}
{{- end -}}

{{- define "file-translation.postgresqlHost" -}}
{{- if .Values.postgresql.external -}}
{{- .Values.postgresql.host -}}
{{- else -}}
{{- include "file-translation.postgresqlName" . -}}
{{- end -}}
{{- end -}}

{{- define "file-translation.minioEndpoint" -}}
{{- if .Values.minio.external -}}
{{- .Values.minio.endpoint -}}
{{- else -}}
{{- printf "http://%s:%v" (include "file-translation.minioName" .) .Values.minio.service.port -}}
{{- end -}}
{{- end -}}

{{- define "file-translation.jobServiceUrl" -}}
{{- printf "http://%s:%v" (include "file-translation.jobServiceName" .) .Values.jobService.service.port -}}
{{- end -}}

{{- define "file-translation.image" -}}
{{- $root := .root -}}
{{- $imageRef := .imageRef -}}
{{- $image := index $root.Values.images $imageRef -}}
{{- $repo := $image.repository -}}
{{- $tag := default $root.Values.images.tag $image.tag -}}
{{- printf "%s:%s" $repo $tag -}}
{{- end -}}

{{- define "file-translation.jobServiceImage" -}}
{{- if .Values.jobService.image.repository -}}
{{- printf "%s:%s" .Values.jobService.image.repository (default .Values.images.tag .Values.jobService.image.tag) -}}
{{- else -}}
{{- include "file-translation.image" (dict "root" . "imageRef" "jobService") -}}
{{- end -}}
{{- end -}}

{{- define "file-translation.imagePullPolicy" -}}
{{- default .Values.global.imagePullPolicy .pullPolicy -}}
{{- end -}}
