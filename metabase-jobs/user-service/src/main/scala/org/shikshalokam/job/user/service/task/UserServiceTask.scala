package org.shikshalokam.job.user.service.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.user.service.domain.Event
import org.shikshalokam.job.user.service.functions.{ProgramServiceFunction, UserServiceFunction}
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class UserServiceTask(config: UserServiceConfig, kafkaConnector: FlinkKafkaConnector) {
  println("Inside UserServiceTask class")

  private val serialVersionUID = -7729362727131516112L

  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    implicit val stringTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])
    val userSource = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopicOne)
    val programSource = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopicTwo)

    if (config.inputTopicOne == config.inputTopicOne) {
      val progressStreamOne = env.addSource(userSource).name(config.userServiceConsumer)
        .uid(config.userServiceConsumer).setParallelism(config.userServiceParallelism).rebalance
        .process(new UserServiceFunction(config))
        .name(config.userServiceFunction).uid(config.userServiceFunction)
        .setParallelism(config.userServiceParallelism)

      progressStreamOne.getSideOutput(config.eventOutputTag)
        .addSink(kafkaConnector.kafkaStringSink(config.outputTopic))
        .name(config.notificationServiceProducer)
        .uid(config.notificationServiceProducer)
        .setParallelism(config.notificationServiceParallelism)
    }

    if (config.inputTopicTwo == config.inputTopicTwo) {
      env.addSource(programSource).name(config.programServiceConsumer)
        .uid(config.programServiceConsumer).setParallelism(config.programServiceParallelism).rebalance
        .process(new ProgramServiceFunction(config))
        .name(config.programServiceFunction).uid(config.programServiceFunction)
        .setParallelism(config.programServiceParallelism)
    }

    env.execute(config.jobName)
  }
}

object UserServiceTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the User Service Job")
    val config = BaseJobConfig.loadConfig(args)
    val userServiceConfig = new UserServiceConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(userServiceConfig)
    val task = new UserServiceTask(userServiceConfig, kafkaUtil)
    task.process()
  }
}