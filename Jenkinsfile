// api-test-platform — Declarative Pipeline
// 插件建议：Pipeline, JUnit, Allure, HTML Publisher, Timestamper, Workspace Cleanup（可选）
// 邮件：安装 Email Extension 后，在 Job / 全局配置 NOTIFY_EMAIL 或凭据

pipeline {
  agent any

  options {
    timestamps()
    timeout(time: 20, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '30', artifactNumToKeepStr: '15'))
    disableConcurrentBuilds()
  }

  parameters {
    choice(
      name: 'TEST_SUITE',
      choices: ['smoke', 'full'],
      description: 'smoke=冒烟(快) / full=全量'
    )
    choice(
      name: 'TEST_ENV',
      choices: ['dev', 'test', 'staging'],
      description: '配置环境名（见 config/settings.py）'
    )
    booleanParam(
      name: 'CLEAN_WORKSPACE',
      defaultValue: false,
      description: '构建前清理工作区（排障时勾选）'
    )
  }

  environment {
    PYTHONUNBUFFERED = '1'
    // 与 config/settings.py 对齐；勿使用 USERNAME（Windows 系统变量）
    TEST_ENV         = "${params.TEST_ENV}"
    // 本地 Mock 用例可不覆盖；对接真实环境时在 Jenkins「凭据 / 环境变量」里注入：
    // API_USERNAME / API_PASSWORD / BASE_URL / AUTH_URL
    PIP_DISABLE_PIP_VERSION_CHECK = '1'
  }

  stages {
    stage('Prepare') {
      steps {
        script {
          if (params.CLEAN_WORKSPACE) {
            cleanWs()
            checkout scm
          }
        }
        echo "SUITE=${params.TEST_SUITE} TEST_ENV=${env.TEST_ENV} NODE=${env.NODE_NAME}"
      }
    }

    stage('Test') {
      steps {
        script {
          if (isUnix()) {
            sh 'chmod +x scripts/ci_test.sh'
            sh "bash scripts/ci_test.sh ${params.TEST_SUITE}"
          } else {
            bat "scripts\\ci_test.bat ${params.TEST_SUITE}"
          }
        }
      }
    }

    stage('Publish') {
      steps {
        // 测试趋势图（失败时仍要归档，所以 post 里也会再调一次 junit）
        junit allowEmptyResults: true, testResults: 'reports/junit.xml'

        // Allure：需安装 Allure Jenkins Plugin；results 目录由 pytest --alluredir 生成
        script {
          try {
            allure([
              includeProperties: false,
              jdk              : '',
              properties       : [],
              reportBuildPolicy: 'ALWAYS',
              results         : [[path: 'allure-results']]
            ])
          } catch (err) {
            echo "Allure 插件未配置或生成失败（可忽略，原始 results 仍会归档）: ${err}"
          }
        }

        archiveArtifacts artifacts: 'reports/**,allure-results/**', allowEmptyArchive: true
      }
    }
  }

  post {
    always {
      // 即使 Publish 阶段前失败，也尽量收集 junit
      junit allowEmptyResults: true, testResults: 'reports/junit.xml'
    }
    success {
      echo "BUILD SUCCESS: ${env.JOB_NAME} #${env.BUILD_NUMBER}"
      script { notifyEmail('SUCCESS') }
    }
    unstable {
      echo "BUILD UNSTABLE (有测试失败)"
      script { notifyEmail('UNSTABLE') }
    }
    failure {
      echo "BUILD FAILURE"
      script { notifyEmail('FAILURE') }
    }
  }
}

// 可选邮件：设置 Job 环境变量 NOTIFY_EMAIL=you@example.com，并配置 Email Extension / SMTP
def notifyEmail(String status) {
  def to = env.NOTIFY_EMAIL
  if (!to) {
    echo 'NOTIFY_EMAIL 未设置，跳过邮件通知'
    return
  }
  try {
    emailext(
      subject: "[${status}] ${env.JOB_NAME} #${env.BUILD_NUMBER}",
      body: """
        <p>状态: <b>${status}</b></p>
        <p>任务: ${env.JOB_NAME} #${env.BUILD_NUMBER}</p>
        <p>套件: ${params.TEST_SUITE} / 环境: ${env.TEST_ENV}</p>
        <p>节点: ${env.NODE_NAME}</p>
        <p><a href="${env.BUILD_URL}">打开构建</a></p>
        <p><a href="${env.BUILD_URL}allure">Allure 报告</a>（若已装插件）</p>
      """,
      mimeType: 'text/html',
      to: to
    )
  } catch (err) {
    echo "邮件发送跳过/失败（检查 Email Extension 与 SMTP）: ${err}"
  }
}
