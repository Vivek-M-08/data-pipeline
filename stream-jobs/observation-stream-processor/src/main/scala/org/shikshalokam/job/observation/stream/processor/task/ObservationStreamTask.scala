package org.shikshalokam.job.observation.stream.processor.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.observation.stream.processor.domain.Event
import org.shikshalokam.job.observation.stream.processor.functions.ObservationStreamFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class ObservationStreamTask(config: ObservationStreamConfig, kafkaConnector: FlinkKafkaConnector) {
  //  private val serialVersionUID = -7729362727131516112L
  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    implicit val stringTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    val progressStream = env.addSource(source).name(config.observationStreamConsumer)
      .uid(config.observationStreamConsumer).setParallelism(config.kafkaConsumerParallelism)
      .rebalance
      .process(new ObservationStreamFunction(config))
      .name(config.observationStreamFunction).uid(config.observationStreamFunction)
      .setParallelism(config.observationStreamParallelism)

    progressStream.getSideOutput(config.eventOutputTag)
      .addSink(kafkaConnector.kafkaStringSink(config.outputTopic))
      .name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer)
      .setParallelism(config.metabaseDashboardParallelism)

    env.execute(config.jobName)
  }
}


object ObservationStreamTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Observation Stream Job")
    val config = BaseJobConfig.loadConfig(args)
    val observationStreamConfig = new ObservationStreamConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(observationStreamConfig)
    val task = new ObservationStreamTask(observationStreamConfig, kafkaUtil)
    task.process()
  }
}