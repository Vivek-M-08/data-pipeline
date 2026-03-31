package org.shikshalokam.job.mentoring.stream.processor.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.mentoring.stream.processor.domain.Event
import org.shikshalokam.job.mentoring.stream.processor.functions.MentoringStreamFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class MentoringStreamTask(config: MentoringStreamConfig, kafkaConnector: FlinkKafkaConnector) {

  private val serialVersionUID = -7729362727131516112L

  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    implicit val stringTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    val progressStream = env.addSource(source).name(config.mentoringStreamConsumer)
      .uid(config.mentoringStreamConsumer).setParallelism(config.kafkaConsumerParallelism)
      .rebalance
      .process(new MentoringStreamFunction(config))
      .name(config.mentoringStreamFunction).uid(config.mentoringStreamFunction)
      .setParallelism(config.mentoringStreamParallelism)

    progressStream.getSideOutput(config.eventOutputTag)
      .addSink(kafkaConnector.kafkaStringSink(config.outputTopic))
      .name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer)
      .setParallelism(config.metabaseDashboardParallelism)

    env.execute(config.jobName)
  }
}

object MentoringStreamTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Mentoring Stream Job")
    val config = BaseJobConfig.loadConfig(args)
    val mentoringStreamConfig = new MentoringStreamConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(mentoringStreamConfig)
    val task = new MentoringStreamTask(mentoringStreamConfig, kafkaUtil)
    task.process()
  }
}