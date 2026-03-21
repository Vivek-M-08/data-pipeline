package org.shikshalokam.job.survey.stream.processor.task

import com.typesafe.config.ConfigFactory
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.shikshalokam.job.BaseJobConfig
import org.apache.flink.streaming.api.scala.StreamExecutionEnvironment
import org.shikshalokam.job.connector.FlinkKafkaConnector
import org.shikshalokam.job.survey.stream.processor.domain.Event
import org.shikshalokam.job.survey.stream.processor.functions.SurveyStreamFunction
import org.shikshalokam.job.util.FlinkUtil

import java.io.File

class SurveyStreamTask(config: SurveyStreamConfig, kafkaConnector: FlinkKafkaConnector){

  private val serialVersionUID = -7729362727131516112L
  def process(): Unit = {
    implicit val env: StreamExecutionEnvironment = FlinkUtil.getExecutionContext(config)
    implicit val eventTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])
    implicit val stringTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])
    val source = kafkaConnector.kafkaJobRequestSource[Event](config.inputTopic)

    val progressStream = env.addSource(source).name(config.surveysStreamConsumer)
      .uid(config.surveysStreamConsumer).setParallelism(config.kafkaConsumerParallelism)
      .rebalance
      .process(new SurveyStreamFunction(config))
      .name(config.surveysStreamFunction).uid(config.surveysStreamFunction)
      .setParallelism(config.surveysStreamParallelism)

    progressStream.getSideOutput(config.eventOutputTag)
      .addSink(kafkaConnector.kafkaStringSink(config.outputTopic))
      .name(config.metabaseDashboardProducer)
      .uid(config.metabaseDashboardProducer)
      .setParallelism(config.metabaseDashboardParallelism)

    env.execute(config.jobName)
  }
}

object SurveyStreamTask {
  def main(args: Array[String]): Unit = {
    println("Starting up the Survey Stream Job")
    val config = BaseJobConfig.loadConfig(args)
    val surveyStreamConfig = new SurveyStreamConfig(config)
    val kafkaUtil = new FlinkKafkaConnector(surveyStreamConfig)
    val task = new SurveyStreamTask(surveyStreamConfig, kafkaUtil)
    task.process()
  }
}