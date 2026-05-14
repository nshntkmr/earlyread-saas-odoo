{{/* ───────────────────────────────────────────────────────────────────────────
     Template helpers for the posterra chart.
     ─────────────────────────────────────────────────────────────────────── */}}

{{/* Chart name. */}}
{{- define "posterra.name" -}}
posterra
{{- end -}}

{{/* Fully-qualified release name. Single-release-per-namespace, so a fixed
     name keeps resource names stable and predictable. */}}
{{- define "posterra.fullname" -}}
posterra
{{- end -}}

{{/* Common metadata labels — applied to every object. */}}
{{- define "posterra.labels" -}}
app.kubernetes.io/name: posterra
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{/* Selector labels — the stable subset used in label selectors. */}}
{{- define "posterra.selectorLabels" -}}
app.kubernetes.io/name: posterra
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/* Common environment block for Odoo containers. Pass the ROOT context ($).
     ODOO_WORKERS / ODOO_MAX_CRON_THREADS / ODOO_EXTRA_ARGS are appended by
     each caller (they differ per role / per job). */}}
{{- define "posterra.commonEnv" -}}
- name: DB_HOST
  value: {{ .Values.database.host | quote }}
- name: DB_PORT
  value: {{ .Values.database.port | quote }}
- name: DB_USER
  value: {{ .Values.database.user | quote }}
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: PG_PASSWORD
- name: ODOO_ADMIN_PASSWORD
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: ODOO_ADMIN_PASSWORD
- name: POSTERRA_JWT_SECRET
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: POSTERRA_JWT_SECRET
- name: POSTERRA_CH_PASSWORD_PROD
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: POSTERRA_CH_PASSWORD_PROD
- name: POSTERRA_AI_API_KEY
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: POSTERRA_AI_API_KEY
- name: POSTERRA_AI_ENDPOINT
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: POSTERRA_AI_ENDPOINT
- name: POSTERRA_AI_MODEL
  valueFrom:
    secretKeyRef:
      name: odoo-secrets
      key: POSTERRA_AI_MODEL
{{- end -}}

{{/* Full pod spec for a serving workload (portal / admin / combined).
     Pass a dict: (dict "root" $ "cfg" <deployment-config>).
       .root — the chart root context ($)
       .cfg  — one entry from .Values.deployments (has workers, maxCronThreads,
               resources, role)
     The init Job and cron StatefulSet do NOT use this — they have their own
     simpler specs (no NGINX sidecar / no static-copy initContainer). */}}
{{- define "posterra.podSpec" -}}
{{- $root := .root -}}
{{- $cfg := .cfg -}}
serviceAccountName: {{ $root.Values.serviceAccount.name }}
initContainers:
  - name: copy-static
    image: "{{ $root.Values.image.repository }}:{{ $root.Values.image.tag }}"
    imagePullPolicy: {{ $root.Values.image.pullPolicy }}
    command:
      - sh
      - -c
      - |
        set -e
        mkdir -p /shared/posterra_portal /shared/dashboard_builder
        cp -r /mnt/extra-addons/posterra_portal/static   /shared/posterra_portal/
        cp -r /mnt/extra-addons/dashboard_builder/static /shared/dashboard_builder/
    volumeMounts:
      - name: shared-static
        mountPath: /shared
containers:
  - name: odoo
    image: "{{ $root.Values.image.repository }}:{{ $root.Values.image.tag }}"
    imagePullPolicy: {{ $root.Values.image.pullPolicy }}
    ports:
      - name: http
        containerPort: 8069
      - name: longpoll
        containerPort: 8072
    env:
      {{- include "posterra.commonEnv" $root | nindent 6 }}
      - name: ODOO_WORKERS
        value: {{ $cfg.workers | quote }}
      - name: ODOO_MAX_CRON_THREADS
        value: {{ $cfg.maxCronThreads | quote }}
    volumeMounts:
      - name: filestore
        mountPath: /var/lib/odoo
    livenessProbe:
      httpGet:
        path: /web/login
        port: 8069
      initialDelaySeconds: 90
      periodSeconds: 30
      failureThreshold: 5
    readinessProbe:
      httpGet:
        path: /web/login
        port: 8069
      initialDelaySeconds: 30
      periodSeconds: 10
      failureThreshold: 3
    resources:
      {{- toYaml $cfg.resources | nindent 6 }}
  - name: nginx
    image: {{ $root.Values.nginx.image | quote }}
    ports:
      - name: web
        containerPort: 8080
    volumeMounts:
      - name: shared-static
        mountPath: /usr/share/nginx/static
        readOnly: true
      - name: nginx-config
        mountPath: /etc/nginx/nginx.conf
        subPath: nginx.conf
        readOnly: true
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 200m
        memory: 128Mi
volumes:
  - name: shared-static
    emptyDir: {}
  - name: nginx-config
    configMap:
      name: {{ include "posterra.fullname" $root }}-nginx
  - name: filestore
    persistentVolumeClaim:
      claimName: {{ include "posterra.fullname" $root }}-filestore
{{- end -}}
