package org.shikshalokam.job

import com.typesafe.config.{Config, ConfigFactory}
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.api.java.utils.ParameterTool
import org.apache.kafka.clients.consumer.ConsumerConfig
import org.apache.kafka.clients.producer.ProducerConfig

import java.io.{File, Serializable}
import java.util.{Base64, Properties}

class BaseJobConfig(val config: Config, val jobName: String) extends Serializable {

  implicit val metricTypeInfo: TypeInformation[String] = TypeExtractor.getForClass(classOf[String])

  val kafkaBrokerServers: String = config.getString("kafka.broker.servers")
  val zookeeper: String = config.getString("kafka.zookeeper")
  val groupId: String = config.getString("kafka.groupId")
  val restartAttempts: Int = config.getInt("task.restart-strategy.attempts")
  val delayBetweenAttempts: Long = config.getLong("task.restart-strategy.delay")
  val parallelism: Int = config.getInt("task.parallelism")

  val kafkaConsumerParallelism: Int = config.getInt("task.consumer.parallelism")
  // Only for Tests
  val kafkaAutoOffsetReset: Option[String] = if (config.hasPath("kafka.auto.offset.reset")) Option(config.getString("kafka.auto.offset.reset")) else None

  // Checkpointing config
  val enableCompressedCheckpointing: Boolean = config.getBoolean("task.checkpointing.compressed")
  val checkpointingInterval: Int = config.getInt("task.checkpointing.interval")
  val checkpointingPauseSeconds: Int = config.getInt("task.checkpointing.pause.between.seconds")
  val enableDistributedCheckpointing: Option[Boolean] = if (config.hasPath("job.enable.distributed.checkpointing")) Option(config.getBoolean("job.enable.distributed.checkpointing")) else None
  val checkpointingBaseUrl: Option[String] = if (config.hasPath("job.statebackend.base.url")) Option(config.getString("job.statebackend.base.url")) else None
  // By default checkpointing timeout is 10 mins
  val checkpointingTimeout: Long = if (config.hasPath("task.checkpointing.timeout")) config.getLong("task.checkpointing.timeout") else 600000L

  def kafkaConsumerProperties: Properties = {
    val properties = new Properties()
    properties.setProperty("bootstrap.servers", kafkaBrokerServers)
    properties.setProperty("group.id", groupId)
    properties.setProperty(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed")
    kafkaAutoOffsetReset.map {
      properties.setProperty("auto.offset.reset", _)
    }
    properties
  }

  def kafkaProducerProperties: Properties = {
    val properties = new Properties()
    properties.setProperty(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, kafkaBrokerServers)
    properties.put(ProducerConfig.LINGER_MS_CONFIG, new Integer(10))
    properties.put(ProducerConfig.BATCH_SIZE_CONFIG, new Integer(16384 * 4))
    properties.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy")
    properties
  }

  def getString(key: String, default: String): String = {
    if (config.hasPath(key)) config.getString(key) else default
  }

  def getInt(key: String, default: Int): Int = {
    if (config.hasPath(key)) config.getInt(key) else default
  }

  def getBoolean(key: String, default: Boolean): Boolean = {
    if (config.hasPath(key)) config.getBoolean(key) else default
  }
}

object BaseJobConfig {
  def loadConfig(args: Array[String]): Config = {
    val parameters = ParameterTool.fromArgs(args)
    if (parameters.has("config.content")) {
      val encodedConfig = parameters.get("config.content")
      val configContent = new String(Base64.getDecoder.decode(encodedConfig))
      ConfigFactory.parseString(configContent).resolve()
    } else if (parameters.has("config.file.path")) {
      val configFilePath = parameters.get("config.file.path")
      ConfigFactory.parseFile(new File(configFilePath)).resolve()
    } else {
      ConfigFactory.load("unified-common.conf").withFallback(ConfigFactory.systemEnvironment())
    }
  }
}
