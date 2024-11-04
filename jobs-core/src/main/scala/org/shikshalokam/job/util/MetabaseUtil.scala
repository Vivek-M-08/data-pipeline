package org.shikshalokam.job.util

class MetabaseUtil(url: String, metabaseUsername: String, metabasePassword: String) {

  private val metabaseUrl: String = url
  private val username: String = metabaseUsername
  private val password: String = metabasePassword
  println("Metabase URL: " + url)
  println("Username: " + username)
  println("Password: " + password)

  private var sessionToken: Option[String] = None

  /**
   * Method to get or refresh the session token
   */
  private def authenticate(): String = {
    val url = s"$metabaseUrl/session"
    val requestBody = s"""{"username": "$username", "password": "$password"}"""

    val response = requests.post(url,
      data = requestBody,
      headers = Map("Content-Type" -> "application/json")
    )
    if (response.statusCode == 200) {
      val token = ujson.read(response.text)("id").str
      token
    } else {
      throw new Exception(s"Authentication failed with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to get or refresh the session token,
   * If cached token is not available get the token from authenticate method.
   */
  private def getSessionToken: String = {
    sessionToken match {
      case Some(token) =>
        //TODO : Remove bellow line
        println(s"SessionToken already exists: $token")
        token
      case None =>
        val token = authenticate()
        //TODO : Remove bellow line
        println(s"Generated new token: $token")
        sessionToken = Some(token)
        token
    }
  }

  /**
   * Method to list collections from Metabase
   *
   * @return JSON string representing the collections
   */
  def listCollections(): String = {
    val url = s"$metabaseUrl/collection"

    val response = requests.get(
      url,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val collectionsJson = ujson.read(response.text).render()
      collectionsJson
    } else {
      throw new Exception(s"Failed to retrieve collections with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to list dashboards from Metabase
   *
   * @return JSON string representing the dashboards
   */
  def listDashboards(): String = {
    val url = s"$metabaseUrl/dashboard"

    val response = requests.get(
      url,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val dashboardsJson = ujson.read(response.text).render()
      dashboardsJson
    } else {
      throw new Exception(s"Failed to retrieve dashboards with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to get dashboard details by Id from Metabase
   *
   * @param dashboardId ID of the dashboard to retrieve details for
   * @return JSON string representing the dashboard details
   */
  def getDashboardDetailsById(dashboardId: Int): String = {
    val url = s"$metabaseUrl/dashboard/$dashboardId"
    val response = requests.get(
      url,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val getDashboardDetailsByIdJson = ujson.read(response.text).render()
      getDashboardDetailsByIdJson
    } else {
      throw new Exception(s"Failed to retrieve dashboard by Id with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to list database details from Metabase
   *
   * @return JSON string representing the database details
   */
  def listDatabaseDetails(): String = {
    val url = s"$metabaseUrl/database"

    val response = requests.get(
      url,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val databasesJson = ujson.read(response.text).render()
      databasesJson
    } else {
      throw new Exception(s"Failed to retrieve database details with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to get database metadata from Metabase
   *
   * @param databaseId ID of the database to retrieve metadata for
   * @return JSON string representing the database metadata
   */
  def getDatabaseMetadata(databaseId: Int): String = {
    val url = s"$metabaseUrl/database/$databaseId/metadata"

    val response = requests.get(
      url,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val databaseMetaDataJson = ujson.read(response.text).render()
      databaseMetaDataJson
    } else {
      throw new Exception(s"Failed to retrieve database metadata with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to create a new collection in Metabase
   *
   * @param requestData JSON string representing the collection data
   * @return JSON string representing the created collection
   */
  def createCollection(requestData: String): String = {
    val url = s"$metabaseUrl/collection"

    val response = requests.post(
      url,
      data = requestData,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val collectionResponseBody = ujson.read(response.text).render()
      collectionResponseBody
    } else {
      throw new Exception(s"Failed to create collection with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to create a new dashboard in Metabase
   *
   * @param requestData JSON string representing the dashboard data
   * @return JSON string representing the created dashboard
   */
  def createDashboard(requestData: String): String = {
    val url = s"$metabaseUrl/dashboard"

    val response = requests.post(
      url,
      data = requestData,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val dashboardResponseBody = ujson.read(response.text).render()
      dashboardResponseBody
    } else {
      throw new Exception(s"Failed to create dashboard with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to create a new question card in Metabase
   *
   * @param requestData JSON string representing the question card data
   * @return JSON string representing the created question card
   */
  def createQuestionCard(requestData: String): String = {
    val url = s"$metabaseUrl/card"

    val response = requests.post(
      url,
      data = requestData,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val questionCardResponseBody = ujson.read(response.text).render()
      questionCardResponseBody
    } else {
      throw new Exception(s"Failed to create question card with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

  /**
   * Method to add a question card to a dashboard in Metabase
   *
   * @param dashboardId ID of the dashboard to add the question card to
   * @param requestData JSON string representing the question card data
   * @return JSON string representing the updated dashboard with the added question card
   */
  def addQuestionCardToDashboard(dashboardId: Int, requestData: String): String = {
    val url = s"$metabaseUrl/dashboard/$dashboardId"

    val response = requests.put(
      url,
      data = requestData,
      headers = Map(
        "Content-Type" -> "application/json",
        "X-Metabase-Session" -> getSessionToken
      )
    )

    if (response.statusCode == 200) {
      val questionCardToDashboardResponseBody = ujson.read(response.text).render()
      questionCardToDashboardResponseBody
    } else {
      throw new Exception(s"Failed to add card to dashboard with status code: ${response.statusCode}, message: ${response.text}")
    }
  }

}
