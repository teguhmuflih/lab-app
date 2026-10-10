// Pipeline Jenkins (fase 8, modul belajar) — padanan job "test" di .github/workflows/ci.yml.
// Jenkins di K3s (namespace jenkins) membuat pod agent per build: container jnlp (agent) + python.
// Job "lab-app" dibuat lewat JCasC/Job DSL di repo lab-gitops (apps/jenkins/values.yaml), poll SCM 15 mnt.
pipeline {
  agent {
    kubernetes {
      defaultContainer 'python'
      yaml '''
apiVersion: v1
kind: Pod
spec:
  containers:
    - name: python
      image: python:3.13-slim-trixie@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
      command: [sleep]
      args: [infinity]
      resources:
        requests: { cpu: 200m, memory: 256Mi }
        limits: { memory: 768Mi }
'''
    }
  }
  options {
    timeout(time: 15, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '20'))
    disableConcurrentBuilds()
  }
  environment {
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
    PIP_NO_CACHE_DIR = '1'
  }
  stages {
    stage('Install') {
      steps {
        sh 'python -m venv .venv && .venv/bin/pip install -q -r requirements-dev.txt'
      }
    }
    stage('Test') {
      steps {
        sh '.venv/bin/pytest -q --junitxml=reports/junit.xml'
      }
      post {
        always { junit 'reports/junit.xml' }
      }
    }
  }
}
