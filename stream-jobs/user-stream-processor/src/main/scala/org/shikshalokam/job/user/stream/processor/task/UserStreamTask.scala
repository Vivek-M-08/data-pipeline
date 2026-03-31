package org.shikshalokam.job.user.stream.processor.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.user.stream.processor.domain.Event
import org.shikshalokam.job.user.stream.processor.functions.UserStreamFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class UserStreamTask(config: UserStreamConfig, kafkaConnector: FlinkKafkaConnector){

  private val serialVersionUID = -7729362727131516112L
  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    implicit val stringTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    val progressStream = env.addSource(source).name(config.usersStreamConsumer)
      .uid(config.usersStreamConsumer).setParallelism(config.kafkaConsumerParallelism)
      .rebalance
      .process(new UserStreamFunction(config))
      .name(config.usersStreamFunction).uid(config.usersStreamFunction)
      .setParallelism(config.usersStreamParallelism)

    progressStream.getSideOutput(config.eventOutputTag)
      .addSink(kafkaConnector.kafkaStringSink(config.outputTopic))
      .name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer)
      .setParallelism(config.metabaseDashboardParallelism)

    // sink for mentoring dashboard events (new)
    progressStream.getSideOutput(config.mentoringEventOutputTag)
      .addSink(kafkaConnector.kafkaStringSink(config.mentoringOutputTopic))
      .name(config.mentoringDashboardProducer)
      .uid(config.mentoringDashboardProducer)
      .setParallelism(config.metabaseDashboardParallelism)

    env.execute(config.jobName)
  }
}

object UserStreamTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the User Stream Job")
    val config = BaseJobConfig.loadConfig(args)
    val userStreamConfig = new UserStreamConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(userStreamConfig)
    val task = new UserStreamTask(userStreamConfig, kafkaUtil)
    task.process()
  }
}