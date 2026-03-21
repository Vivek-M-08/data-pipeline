package org.shikshalokam.job.observation.dashboard.creator.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.observation.dashboard.creator.domain.Event
import org.shikshalokam.job.observation.dashboard.creator.functions.ObservationMetabaseDashboardFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class ObservationMetabaseDashboardTask(config: ObservationMetabaseDashboardConfig, kafkaConnector: FlinkKafkaConnector) {
  println("inside MetabaseDashboardTask class")

  private val serialVersionUID = -7729362727131516112L

  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    env.addSource(source).name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer).setParallelism(config.mlMetabaseParallelism).rebalance
      .process(new ObservationMetabaseDashboardFunction(config))
      .name(config.metabaseDashboardFunction).uid(config.metabaseDashboardFunction)
      .setParallelism(config.mlMetabaseParallelism)

    env.execute(config.jobName)
  }
}

object ObservationMetabaseDashboardTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Metabase Dashboard creation Job")
    val config = BaseJobConfig.loadConfig(args)
    val metabaseDashboardConfig = new ObservationMetabaseDashboardConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(metabaseDashboardConfig)
    val task = new ObservationMetabaseDashboardTask(metabaseDashboardConfig, kafkaUtil)
    task.process()
  }
}