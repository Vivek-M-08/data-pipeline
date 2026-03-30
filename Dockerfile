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
    unzip \
    tmux \
    maven \
    tmux \
    jq \
    nano \
    postgresql postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set Java environment variables
RUN apt update && apt install -y openjdk-11-jdk && \
    JAVA_HOME=$(dirname $(dirname $(readlink -f $(which javac)))) && \
    echo "export JAVA_HOME=$JAVA_HOME" >> /etc/profile && \
    echo "export PATH=$JAVA_HOME/bin:$PATH" >> /etc/profile && \
    ln -s $JAVA_HOME /usr/lib/jvm/default-java

ENV JAVA_HOME=/usr/lib/jvm/default-java
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
RUN MAVEN_VERSION=$(curl -s https://maven.apache.org/download.cgi | grep -oP 'apache-maven-\K[0-9.]+(?=-bin\.tar\.gz)' | head -1) && \
    wget https://downloads.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz && \
    tar -xzf apache-maven-${MAVEN_VERSION}-bin.tar.gz && \
    mv apache-maven-${MAVEN_VERSION} /usr/local/maven && \
    rm apache-maven-${MAVEN_VERSION}-bin.tar.gz

ENV MAVEN_HOME=/usr/local/maven
ENV PATH=$MAVEN_HOME/bin:$PATH

# Install Python 3.12.6
RUN apt update && apt install -y software-properties-common curl \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt update \
    && apt install -y python3.12 python3.12-venv \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2 \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python3

ENV PATH="/usr/local/bin:$PATH"

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r /app/requirements.txt

RUN mvn clean install -DskipTests

# Set default command
CMD ["tail", "-f", "/dev/null"]