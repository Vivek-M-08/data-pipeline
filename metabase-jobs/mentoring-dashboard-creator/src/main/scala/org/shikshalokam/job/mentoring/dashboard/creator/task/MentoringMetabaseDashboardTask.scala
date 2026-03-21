package org.shikshalokam.job.mentoring.dashboard.creator.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.mentoring.dashboard.creator.domain.Event
import org.shikshalokam.job.mentoring.dashboard.creator.functions.MentoringMetabaseDashboardFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class MentoringMetabaseDashboardTask(config: MentoringMetabaseDashboardConfig, kafkaConnector: FlinkKafkaConnector) {
  println("inside MentoringMetabaseDashboardTask class")

  private val serialVersionUID = -7729362727131516112L

  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    env.addSource(source).name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer).setParallelism(config.mlMetabaseParallelism).rebalance
      .process(new MentoringMetabaseDashboardFunction(config))
      .name(config.metabaseDashboardFunction).uid(config.metabaseDashboardFunction)
      .setParallelism(config.mlMetabaseParallelism)

    env.execute(config.jobName)
  }
}

object MentoringMetabaseDashboardTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Metabase Dashboard creation Job")
    val config = BaseJobConfig.loadConfig(args)
    val metabaseDashboardConfig = new MentoringMetabaseDashboardConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(metabaseDashboardConfig)
    val task = new MentoringMetabaseDashboardTask(metabaseDashboardConfig, kafkaUtil)
    task.process()
  }
}