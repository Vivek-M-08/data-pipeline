package org.shikshalokam.job.dashboard.creator.domain

import org.shikshalokam.job.domain.reader.JobRequest

class Event(eventMap: java.util.Map[String, Any], partition: Int, offset: Long) extends JobRequest(eventMap, partition, offset) {

  def _id: String = readOrDefault[String]("_id", "")

  def reportType: String = readOrDefault[String]("reportType", null)

  def dashboardData: Map[String, String] = readOrDefault[Map[String, String]]("dashboardData", null)

//  def projectAdmin: String = readOrDefault[String]("dashboardData.admin", null)
//
//  def targetedProgram: String = readOrDefault[String]("dashboardData.targetedProgram", null)
//
//  def targetedState: String = readOrDefault[String]("dashboardData.targetedState", null)
//
//  def targetedDistrict: String = readOrDefault[String]("dashboardData.targetedDistrict", null)

}
