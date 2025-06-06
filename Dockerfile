# Use Ubuntu as base image
FROM ubuntu:22.04

# Set non-interactive mode to avoid timezone prompts
ENV DEBIAN_FRONTEND=noninteractive

# Update packages and install required dependencies
RUN apt update && apt install -y \
    openjdk-11-jdk \
    wget \
    tar \
    git \
    curl \
    maven \
    jq \
    postgresql postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set Java environment variables
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"

# Download and install Scala
WORKDIR /usr/local
RUN wget https://downloads.lightbend.com/scala/2.12.11/scala-2.12.11.tgz \
    && tar -xzf scala-2.12.11.tgz \
    && mv scala-2.12.11 scala \
    && rm scala-2.12.11.tgz

# Set Scala environment variables
ENV SCALA_HOME=/usr/local/scala
ENV PATH="$SCALA_HOME/bin:$PATH"

# Install Maven
RUN wget https://downloads.apache.org/maven/maven-3/3.8.8/binaries/apache-maven-3.8.8-bin.tar.gz && \
    tar -xzf apache-maven-3.8.8-bin.tar.gz && \
    mv apache-maven-3.8.8 /usr/local/maven && \
    rm apache-maven-3.8.8-bin.tar.gz

ENV MAVEN_HOME=/usr/local/maven
ENV PATH=$MAVEN_HOME/bin:$PATH


WORKDIR /app

COPY . /app

RUN mvn clean install -DskipTests

# Set default command
CMD ["tail", "-f", "/dev/null"]
