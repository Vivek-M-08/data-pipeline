package org.shikshalokam.job.akkaservice.routes

import akka.http.scaladsl.model.{ContentTypes, HttpEntity, StatusCodes}
import akka.http.scaladsl.server.Directives._
import akka.http.scaladsl.server.Route
import org.shikshalokam.job.akkaservice.controllers.AppController
import org.shikshalokam.job.akkaservice.config.AppConfig
import java.security.MessageDigest

object Routes {

  private val config = AppConfig.config
  private val apiToken = config.getString("akka.security.api.token")

  def route: Route =
    concat(
      path("health") {
        get {
          complete(HttpEntity(ContentTypes.`application/json`, """{"status":"UP"}"""))
        }
      },
      pathPrefix("api") {
        concat(
          // CSV Routes
          pathPrefix("csv") {
            headerValueByName("Authorization") { token =>
              if (secureEquals(token, apiToken)) {
                concat(
                  path("upload") {
                    post(AppController.uploadCsvFile)
                  },
                  path("list") {
                    get(AppController.listUploadedCsvFiles)
                  }
                )
              } else {
                complete((StatusCodes.Unauthorized, "Invalid or missing token"))
              }
            }
          },
          // Health Check Routes
          pathPrefix("health") {
            headerValueByName("Authorization") { token =>
              if (secureEquals(token, apiToken)) {
                concat(
                  pathEndOrSingleSlash {
                    get(AppController.healthCheck)
                  },
                  path(Segment) { service =>
                    get(AppController.serviceHealthCheck(service))
                  }
                )
              } else {
                complete((StatusCodes.Unauthorized, "Invalid or missing token"))
              }
            }
          }
        )
      }
    )

  private def secureEquals(a: String, b: String): Boolean = {
    MessageDigest.isEqual(a.getBytes("UTF-8"), b.getBytes("UTF-8"))
  }
}
