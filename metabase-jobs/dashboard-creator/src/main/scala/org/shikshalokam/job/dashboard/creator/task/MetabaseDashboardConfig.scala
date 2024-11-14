package org.shikshalokam.job.dashboard.creator.task

import com.typesafe.config.Config
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.shikshalokam.job.BaseJobConfig
import org.shikshalokam.job.dashboard.creator.domain.Event


class MetabaseDashboardConfig(override val config: Config) extends BaseJobConfig(config, "MetabaseDashboardJob") {

  implicit val mapTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])

  // Kafka Topics Configuration
  val inputTopic: String = config.getString("kafka.input.topic")

  // Parallelism
  val mlMetabaseParallelism: Int = config.getInt("task.sl.metabase.dashboard.parallelism")

  // Consumers
  val metabaseDashboardProducer: String = "metabase-dashboard-consumer"

  // Functions
  val metabaseDashboardFunction: String = "MetabaseDashboardFunction"

  // Metabase Dashboard submissions job metrics
  val metabaseDashboardCleanupHit = "metabase-dashboard-cleanup-hit"
  val skipCount = "skipped-message-count"
  val successCount = "success-message-count"
  val totalEventsCount = "total-metabase-dashboard-events-count"

  // PostgreSQL connection config
  val pgHost: String = config.getString("postgres.host")
  val pgPort: String = config.getString("postgres.port")
  val pgUsername: String = config.getString("postgres.username")
  val pgPassword: String = config.getString("postgres.password")
  val pgDataBase: String = config.getString("postgres.database")

  // Metabase connection config
  val metabaseUrl: String = config.getString("metabase.url")
  val metabaseUsername: String = config.getString("metabase.username")
  val metabasePassword: String = config.getString("metabase.password")
  val metabaseDatabase: String = config.getString("metabase.database")

}
