package org.shikshalokam.job.dashboard.creator.functions

import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.configuration.Configuration
import org.apache.flink.streaming.api.functions.ProcessFunction
import org.shikshalokam.job.BaseProcessFunction
import org.shikshalokam.job.dashboard.creator.common.Helpers
import org.shikshalokam.job.dashboard.creator.domain.Event
import org.shikshalokam.job.util.PostgresUtil
import org.shikshalokam.job.dashboard.creator.task.MetabaseDashboardConfig
import org.shikshalokam.job.util.{MetabaseUtil, PostgresUtil}
import org.shikshalokam.job.{BaseProcessFunction, Metrics}
import org.slf4j.LoggerFactory

import scala.collection.immutable._

class MetabaseDashboardFunction(config: MetabaseDashboardConfig)(implicit val mapTypeInfo: TypeInformation[Event], @transient var postgresUtil: PostgresUtil = null, @transient var metabaseUtil: MetabaseUtil = null)
  extends BaseProcessFunction[Event, Event](config) {

  private[this] val logger = LoggerFactory.getLogger(classOf[MetabaseDashboardFunction])

  override def metricsList(): List[String] = {
    List(config.metabaseDashboardCleanupHit, config.skipCount, config.successCount, config.totalEventsCount)
  }

  override def open(parameters: Configuration): Unit = {
    super.open(parameters)
    val pgHost: String = config.pgHost
    val pgPort: String = config.pgPort
    val pgUsername: String = config.pgUsername
    val pgPassword: String = config.pgPassword
    val pgDataBase: String = config.pgDataBase
    val metabaseUrl: String = config.metabaseUrl
    val metabaseUsername: String = config.metabaseUsername
    val metabasePassword: String = config.metabasePassword
    val connectionUrl: String = s"jdbc:postgresql://$pgHost:$pgPort/$pgDataBase"
    postgresUtil = new PostgresUtil(connectionUrl, pgUsername, pgPassword)
    metabaseUtil = new MetabaseUtil(metabaseUrl, metabaseUsername, metabasePassword)
  }

  override def close(): Unit = {
    super.close()
  }

  override def processElement(event: Event, context: ProcessFunction[Event, Event]#Context, metrics: Metrics): Unit = {
    println(s"***************** Start of Processing the Metabase Dashboard Event with Id = ${event._id}*****************")

    println("dashboard data ====>>> " + event.dashboardData)

    event.reportType match {
      case "Project" =>
        println("Processing the Project Dashboard Creation request")
        processProjectReports(event.dashboardData, event.reportType)

      case "Survey" =>
        println("Processing the Survey Dashboard Creation request")
      //TODO: Call a survey object to create survey dashboard

      case "Observation" =>
        println("Processing the Observation Dashboard Creation request")
      //TODO: Call a observation object to create observation dashboard

      case _ =>
        println("Report Type is not valid")
    }

    println(s"***************** End of Processing the Metabase Dashboard Event *****************\n")
  }

  private def processProjectReports(dashboardData: Map[String, String], reportType: String): Unit = {
    val metabaseDatabase: String = config.metabaseDatabase
    val admin = dashboardData.getOrElse("admin", null)
    val targetedProgram = dashboardData.getOrElse("targetedProgram", null)
    val targetedState = dashboardData.getOrElse("targetedState", null)
    val targetedDistrict = dashboardData.getOrElse("targetedDistrict", null)

    if (admin != null) {
      println("\n\n\n")
      println(s"Admin = $admin")
      val collectionName: String = s"Admin Collection"
      val dashboardName: String = s"$reportType Admin Report"
//      val collectionId = Helpers.checkAndCreateCollection(collectionName, metabaseUtil, postgresUtil)
//      val dashboardId = Helpers.checkAndCreateDashboard(collectionId, dashboardName, metabaseUtil, postgresUtil)
      val databaseId = Helpers.getDatabaseId(metabaseDatabase, metabaseUtil)
      val stateFilterColumnId = Helpers.getTableMetadataId(databaseId, metabaseUtil, "projects", "statename")
      val districtFilterColumnId = Helpers.getTableMetadataId(databaseId, metabaseUtil, "projects", "districtname")
      val programFilterColumnId = Helpers.getTableMetadataId(databaseId, metabaseUtil, "solutions", "programname")

    }


//    if (targetedProgram != null) println(s"Targeted Program = $targetedProgram")
//    if (targetedState != null) println(s"Targeted State = $targetedState")
//    if (targetedDistrict != null) println(s"Targeted District = $targetedDistrict")

  }


}
