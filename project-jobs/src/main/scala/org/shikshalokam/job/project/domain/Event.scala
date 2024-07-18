package org.shikshalokam.job.project.domain

import org.shikshalokam.job.domain.reader.JobRequest

class Event(eventMap: java.util.Map[String, Any], partition: Int, offset: Long) extends JobRequest(eventMap, partition, offset) {

  println("inside event ")
  def solutionId: String = readOrDefault[String]("solutionInformation._id", "")
  def solutionExternalId: String = readOrDefault[String]("solutionInformation.externalId", "")
  def solutionName: String = readOrDefault[String]("solutionInformation.name", "")
  def solutionDescription: String = readOrDefault[String]("solutionInformation.description", "")

  def projectDuration: String = readOrDefault[String]("metaInformation.duration", "")
  def hasAcceptedTAndC: Boolean = readOrDefault[Boolean]("hasAcceptedTAndC", false)
  def projectIsDeleted: Boolean = readOrDefault[Boolean]("isDeleted", false)
  def projectCreatedType: String = if (readOrDefault[String]("projectTemplateId", "").nonEmpty) "project imported from library" else "user created project"
  def privateProgram: Boolean = readOrDefault[Boolean]("isAPrivateProgram", false)

  def programId: String = readOrDefault[String]("programInformation._id", "")
  def programExternalId: String = readOrDefault[String]("programInformation.externalId", "")
  def programName: String = readOrDefault[String]("programInformation.name", "")
  def programDescription: String = readOrDefault[String]("programInformation.description", "")



  def projectId: String = readOrDefault[String]("_id", "")
  def createdBy: String = readOrDefault[String]("createdBy", "")
  def completedDate: String = if (readOrDefault[String]("status", "") == "submitted") readOrDefault[String]("updatedAt", "None") else "None"
  def createdAt: String = readOrDefault[String]("createdAt", "")
  def projectEvidences: List[Map[String, Any]] = readOrDefault[List[Map[String, Any]]]("attachments", null)
//  def evidenceCount
  def projectLastSync: String = readOrDefault[String]("syncedAt", "")
//  def projectRemarks: String = readOrDefault[String]("syncedAt", "")
  def projectUpdatedDate: String = readOrDefault[String]("updatedAt", "")
  def projectStatus: String = readOrDefault[String]("status", "")

  println("\n")
  println("solutionId = " + solutionId)
  println("solutionExternalId = " + solutionExternalId)
  println("solutionName = " + solutionName)
  println("solutionDescription = " + solutionDescription)

  println("\n")
  println("projectDuration = " + projectDuration)
  println("hasAcceptedTAndC = " + hasAcceptedTAndC)
  println("projectIsDeleted = " + projectIsDeleted)
  println("projectCreatedType = " + projectCreatedType)
  println("privateProgram = " + privateProgram)

  println("\n")
  println("programId = " + programId)
  println("programExternalId = " + programExternalId)
  println("programName = " + programName)
  println("programDescription = " + programDescription)

  println("\n")
  println("projectId = " + projectId)
  println("createdBy = " + createdBy)
  println("completedDate = " + completedDate)
  println("createdAt = " + createdAt)
  println("projectEvidences = "+ projectEvidences)
  println("projectLastSync = "+ projectLastSync)
  println("projectUpdatedDate = "+ projectUpdatedDate)
  println("projectStatus = "+ projectStatus)


}
