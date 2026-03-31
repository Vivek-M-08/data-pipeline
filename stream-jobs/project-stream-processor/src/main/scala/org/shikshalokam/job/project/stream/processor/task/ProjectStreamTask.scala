package org.shikshalokam.job.project.stream.processor.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.project.stream.processor.domain.Event
import org.shikshalokam.job.project.stream.processor.functions.ProjectStreamFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class ProjectStreamTask(config: ProjectStreamConfig, kafkaConnector: FlinkKafkaConnector){

  private val serialVersionUID = -7729362727131516112L
  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    implicit val stringTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    val progressStream = env.addSource(source).name(config.projectsStreamConsumer)
      .uid(config.projectsStreamConsumer).setParallelism(config.kafkaConsumerParallelism)
      .rebalance
      .process(new ProjectStreamFunction(config))
      .name(config.projectsStreamFunction).uid(config.projectsStreamFunction)
      .setParallelism(config.projectsStreamParallelism)

    progressStream.getSideOutput(config.eventOutputTag)
      .addSink(kafkaConnector.kafkaStringSink(config.outputTopic))
      .name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer)
      .setParallelism(config.metabaseDashboardParallelism)

    env.execute(config.jobName)
  }
}

object ProjectStreamTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Project Stream Job")
    val config = BaseJobConfig.loadConfig(args)
    val projectStreamConfig = new ProjectStreamConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(projectStreamConfig)
    val task = new ProjectStreamTask(projectStreamConfig, kafkaUtil)
    task.process()
  }
}