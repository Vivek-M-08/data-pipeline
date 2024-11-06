package org.shikshalokam.job.dashboard.creator.functions

import org.apache.flink.api.common.typeinfo.TypeInformation
import org.apache.flink.configuration.Configuration
import org.apache.flink.streaming.api.functions.ProcessFunction
import org.shikshalokam.job.BaseProcessFunction
import org.shikshalokam.job.dashboard.creator.domain.Event
import org.shikshalokam.job.util.PostgresUtil
import org.shikshalokam.job.dashboard.creator.task.MetabaseDashboardConfig
import org.shikshalokam.job.util.{MetabaseUtil, PostgresUtil}
import org.shikshalokam.job.{BaseProcessFunction, Metrics}
import org.slf4j.LoggerFactory
import play.api.libs.json._

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

    println("reportType = " + event.reportType)
    println("admin = " + event.admin)
    println("targetedProgram = " + event.targetedProgram )
    println("targetedDistrict = " + event.targetedDistrict)
    println("targetedState = " + event.targetedState)
    println("publishedAt = " + event.publishedAt)

    if (event.reportType == "Project") {
      var ReportType = event.reportType
      if (event.admin == List("Admin")) {
        val listCollections = metabaseUtil.listCollections()
        // Parse the JSON string
        val json = Json.parse(listCollections)

        // Check if any collection contains "name": "Super Admin Collection"
        val exists = (json \\ "name").exists(name => name.as[String].trim == "Super Admin Collection")

        if (exists) {
          println("Super Admin Collection exists in the list.")
        } else {
          println("Super Admin Collection does not exist in the list.")
        }

      }
      // let's create state report
      for (state <- event.targetedState) {
        // get the collection id
        val collection_name = s"state collection [$state]"
        val collectionRequestBody =
          s"""{
            |  "name": "$collection_name",
            |  "description": "Collection for $ReportType reports"
            |}""".stripMargin
        val collection = metabaseUtil.createCollection(collectionRequestBody)
        val collectionJson: JsValue = Json.parse(collection)
//        println("collectionJson = " + collectionJson)
        val collectionId: Int = (collectionJson \ "id").asOpt[Int].getOrElse {
          throw new Exception("Failed to extract collection id")
        }
        println("CollectionId = " + collectionId)

        //get the dashboard id
        val dashboard_name = s"state report [$state]"
        val dashboardRequestBody =
          s"""{
            |  "name": "$dashboard_name",
            |  "collection_id": "$collectionId"
            |}""".stripMargin
        val Dashboard = metabaseUtil.createDashboard(dashboardRequestBody)
        println("Create Dashboard Json = " + Dashboard)

        //get database id
        val listDatabaseDetails = metabaseUtil.listDatabaseDetails()
        println("Database Details JSON = " + listDatabaseDetails)
        // function to fetch database id from the output of listDatabaseDetails API
        def getDatabaseId(databasesResponse: String, databaseName: String): Option[Int] = {
          val json = Json.parse(databasesResponse)

          // Extract the ID of the database with the given name
          (json \ "data").as[Seq[JsValue]].find { db =>
            (db \ "name").asOpt[String].contains(databaseName)
          }.flatMap { db =>
            (db \ "id").asOpt[Int]
          }
        }

        val databaseName: String = config.metabaseDatabase
        val databaseId = getDatabaseId(listDatabaseDetails, databaseName).get
        println("databaseId = " + databaseId)

        //Update the question cards with the collection id , database id


      }
    }


    //TODO: Remove the below lines and build actual logic
//    val listCollections = metabaseUtil.listCollections()
//    println("Collections JSON = " + listCollections)

//    val listDashboards = metabaseUtil.listDashboards()
//    println("Dashboards JSON = " + listDashboards)

//    val getDashboardInfo = metabaseUtil.getDashboardDetailsById(257)
//    println("Dashboard Info JSON = " + getDashboardInfo)

//    val listDatabaseDetails = metabaseUtil.listDatabaseDetails()
//    println("Database Details JSON = " + listDatabaseDetails)

//    val getDatabaseMetadata = metabaseUtil.getDatabaseMetadata(34)
//    println("Database Metadata JSON = " + getDatabaseMetadata)

//    val collectionRequestBody =
//      """{
//        |  "name": "New Collection",
//        |  "description": "Collection for project reports"
//        |}""".stripMargin
//    val createColelction = metabaseUtil.createCollection(collectionRequestBody)
//    println("Create Collection JSON = " + createColelction)
//
//
//    val dashboardRequestBody =
//      """{
//        |  "name": "New Dashboard1",
//        |  "collection_id": "273"
//        |}""".stripMargin
//    val createDashboard = metabaseUtil.createDashboard(dashboardRequestBody)
//    println("Create Dashboard Json = " + createDashboard)
//
//    val questionCardRequestBody =
//      """{
//        |    "name": "No. of improvements in inProgress status currently",
//        |    "collection_id": 273,
//        |    "dataset_query": {
//        |        "database": 34,
//        |        "type": "native",
//        |        "native": {
//        |            "query": "SELECT\n  COUNT(DISTINCT projects.projectid) AS \"no_of_projects_inprogress\"\nFROM\n  projects\nJOIN solutions on projects.solutionid = solutions.solutionid\nWHERE\nprojects.status = 'inProgress'\n[[AND {{state_param}} ]]\n[[AND {{district_param}}]]\n[[AND {{program_param}}]]",
//        |            "template-tags": {
//        |                "state_param": {
//        |                    "type": "dimension",
//        |                    "name": "state_param",
//        |                    "display-name": "State Param",
//        |                    "default": null,
//        |                    "dimension": [
//        |                        "field",
//        |                        189,
//        |                        null
//        |                    ],
//        |                    "widget-type": "string/=",
//        |                    "options": null
//        |                },
//        |                "district_param": {
//        |                    "type": "dimension",
//        |                    "name": "district_param",
//        |                    "display-name": "District Param",
//        |                    "default": null,
//        |                    "dimension": [
//        |                        "field",
//        |                        196,
//        |                        null
//        |                    ],
//        |                    "widget-type": "string/=",
//        |                    "options": null
//        |                },
//        |                "program_param": {
//        |                    "type": "dimension",
//        |                    "name": "program_param",
//        |                    "display-name": "Program Param",
//        |                    "default": null,
//        |                    "dimension": [
//        |                        "field",
//        |                        173,
//        |                        null
//        |                    ],
//        |                    "widget-type": "string/=",
//        |                    "options": null
//        |                }
//        |            }
//        |        }
//        |    },
//        |    "display": "scalar",
//        |    "visualization_settings": {},
//        |    "parameters": [
//        |        {
//        |            "id": "state_param",
//        |            "type": "string/=",
//        |            "target": [
//        |                "dimension",
//        |                [
//        |                    "template-tag",
//        |                    "state_param"
//        |                ]
//        |            ],
//        |            "name": "State Param"
//        |        },
//        |        {
//        |            "id": "district_param",
//        |            "type": "string/=",
//        |            "target": [
//        |                "dimension",
//        |                [
//        |                    "template-tag",
//        |                    "district_param"
//        |                ]
//        |            ],
//        |            "name": "District Param"
//        |        },
//        |        {
//        |            "id": "program_param",
//        |            "type": "string/=",
//        |            "target": [
//        |                "dimension",
//        |                [
//        |                    "template-tag",
//        |                    "program_param"
//        |                ]
//        |            ],
//        |            "name": "Program Param"
//        |        }
//        |    ]
//        |}""".stripMargin
//
//    val createQuestionCard = metabaseUtil.createQuestionCard(questionCardRequestBody)
//    println("Create Question Card Json = " + createQuestionCard)
//
//
//    val addQuestionToDashboardRequestBody =
//      """{
//        |    "card_id": 654,
//        |    "dashboard_tab_id": null,
//        |    "id": 2,
//        |    "col": 6,
//        |    "row": 0,
//        |    "size_x": 6,
//        |    "size_y": 3,
//        |    "visualization_settings": {},
//        |    "parameter_mappings": [
//        |        {
//        |            "parameter_id": "c32c8fc5",
//        |            "card_id": 654,
//        |            "target": [
//        |                "dimension",
//        |                [
//        |                    "template-tag",
//        |                    "state_param"
//        |                ]
//        |            ]
//        |        },
//        |        {
//        |            "parameter_id": "74a10335",
//        |            "card_id": 654,
//        |            "target": [
//        |                "dimension",
//        |                [
//        |                    "template-tag",
//        |                    "district_param"
//        |                ]
//        |            ]
//        |        },
//        |        {
//        |            "parameter_id": "8c7d86ea",
//        |            "card_id": 654,
//        |            "target": [
//        |                "dimension",
//        |                [
//        |                    "template-tag",
//        |                    "program_param"
//        |                ]
//        |            ]
//        |        }
//        |    ]
//        |}
//        |""".stripMargin
//
//    val addQuestionToDashboard = metabaseUtil.addQuestionCardToDashboard(257, addQuestionToDashboardRequestBody)
//    println("Add Question To Dashboard Json = " + addQuestionToDashboard)

    println(s"***************** End of Processing the Metabase Dashboard Event *****************\n")
  }
}
