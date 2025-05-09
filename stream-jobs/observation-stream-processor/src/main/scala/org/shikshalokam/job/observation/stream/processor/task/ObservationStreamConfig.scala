package org.shikshalokam.job.observation.stream.processor.task

import com.typesafe.config.Config
import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.api.java.typeutils.TypeExtractor
import org.apache.flink.streaming.api.scala.OutputTag
import org.shikshalokam.job.observation.stream.processor.domain.Event
import org.shikshalokam.job.BaseJobConfig
import scala.collection.JavaConverters._

class ObservationStreamConfig(override val config: Config) extends BaseJobConfig(config, "ObservationsStreamJob") {

  implicit val mapTypeInfo: TypeInformation[Event] = TypeExtractor.getForClass(classOf[Event])

  // Kafka Topics Configuration
  val inputTopic: String = config.getString("kafka.input.topic")
  val outputTopic: String = config.getString("kafka.output.topic")

  // Output Tags
  val eventOutputTag: OutputTag[String] = OutputTag[String]("observation-dashboard-output-event")

  // Parallelism
  override val kafkaConsumerParallelism: Int = config.getInt("task.consumer.parallelism")
  val observationStreamParallelism: Int = config.getInt("task.sl.observation.stream.parallelism")
  val metabaseDashboardParallelism: Int = config.getInt("task.sl.metabase.observation.dashboard.parallelism")

  // Consumers
  val observationStreamConsumer: String = "observation-stream-consumer"
  val metabaseDashboardProducer = "metabase-observation-dashboard-producer"

  // Functions
  val observationStreamFunction: String = "ObservationStreamFunction"

  // Observation submissions job metrics
  val observationCleanupHit = "observation-cleanup-hit"
  val skipCount = "skipped-message-count"
  val successCount = "success-message-count"
  val totalEventsCount = "total-observation-events-count"

  //report-config
  val reportsEnabled: Set[String]= config.getStringList("reports.enabled").asScala.toSet

  // PostgreSQL connection config
  val pgHost: String = config.getString("postgres.host")
  val pgPort: String = config.getString("postgres.port")
  val pgUsername: String = config.getString("postgres.username")
  val pgPassword: String = config.getString("postgres.password")
  val pgDataBase: String = config.getString("postgres.database")
//  val solutions: String = config.getString("postgres.tables.solutionsTable")
  val dashboard_metadata: String = config.getString("postgres.tables.dashboardMetadataTable")

//  val createSolutionsTable =
//    s"""CREATE TABLE IF NOT EXISTS $solutions (
//       |    solution_id TEXT PRIMARY KEY,
//       |    external_id TEXT,
//       |    name TEXT,
//       |    description TEXT,
//       |    duration TEXT,
//       |    categories TEXT,
//       |    program_id TEXT,
//       |    program_name TEXT,
//       |    program_external_id TEXT,
//       |    program_description TEXT,
//       |    private_program BOOLEAN
//       |);""".stripMargin
//
//  val createDashboardMetadataTable =
//    s"""CREATE TABLE IF NOT EXISTS $dashboard_metadata (
//       |    id SERIAL PRIMARY KEY,
//       |    entity_type TEXT NOT NULL,
//       |    entity_name TEXT NOT NULL,
//       |    entity_id TEXT UNIQUE NOT NULL,
//       |    collection_id TEXT,
//       |    dashboard_id TEXT,
//       |    question_ids TEXT,
//       |    status TEXT,
//       |    error_message TEXT
//       |);
//       |""".stripMargin

}