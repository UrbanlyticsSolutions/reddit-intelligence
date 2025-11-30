# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Create the outputs directory
RUN mkdir -p outputs

# Define environment variable for unbuffered output
ENV PYTHONUNBUFFERED=1

# Run the workflow script when the container launches
# Default to comprehensive analysis for the day
ENTRYPOINT ["python", "main.py"]
CMD ["--no-deploy", "--horizon", "day"]
