package org.shikshalokam.job.survey.dashboard.creator.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.survey.dashboard.creator.domain.Event
import org.shikshalokam.job.survey.dashboard.creator.functions.SurveyMetabaseDashboardFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class MetabaseDashboardTask(config: SurveyMetabaseDashboardConfig, kafkaConnector: FlinkKafkaConnector) {
  println("inside MetabaseDashboardTask class")

  private val serialVersionUID = -7729362727131516112L

  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    env.addSource(source).name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer).setParallelism(config.mlMetabaseParallelism).rebalance
      .process(new SurveyMetabaseDashboardFunction(config))
      .name(config.metabaseDashboardFunction).uid(config.metabaseDashboardFunction)
      .setParallelism(config.mlMetabaseParallelism)

    env.execute(config.jobName)
  }
}

object MetabaseDashboardTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Metabase Dashboard creation Job")
    val config = BaseJobConfig.loadConfig(args)
    val metabaseDashboardConfig = new SurveyMetabaseDashboardConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(metabaseDashboardConfig)
    val task = new MetabaseDashboardTask(metabaseDashboardConfig, kafkaUtil)
    task.process()
  }
}