#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
import docker
import os
import sys

###############################################
#
#
#   Global Variables / Config
#
#
###############################################

image_name = "beeven/docker-sqlcmd"

###############################################
#
#
#   Helpers
#
#
###############################################


###############################################

@click.group()
def sqlcmd(help="A command line interface for querying the anpr mssql database server"):
    pass

@sqlcmd.command('pull-image', help="Pull the sqlcmd docker image")
def pull():
    client = docker.APIClient(base_url='unix://var/run/docker.sock')
    if not client.images(name = image_name):
        click.echo("Pulling " + image_name + " docker image, this may take a while...")
        iterator = client.pull(image_name, tag = "latest", stream = True)
        printStream(iterator)
        click.echo("Done")
    else:
        click.echo("Skipped: image exists")


@sqlcmd.command('query', help="Query the anpr database server")
@click.option('--password', '-p',
	     type = str,
	     envvar = 'SQL_PASSWORD',
	     required = True,
             help="Database password. Read from the environment variable 'SQL_PASSWORD'")
@click.option('--query-string', '-q', type = str, default = None, required = False, help="The sql query as a string")
@click.option('--output-file', '-o', type = str, default = None, required = False, help="Write results to output file")
@click.option('--prune/--no-prune', default=True, required = False, help="Remove trailing whitespace, dash separator, etc.")
@click.option('--query-file', '-i', type = str, default = None, required = False, help="Read the query from file")
@click.option('--host', '-t', type = str, default = '127.0.0.1', required = False, help="Database server IP address")
def query_anpr(query_string, output_file, query_file, password, prune, host):
    client = docker.from_env()
    # Get image, otherwise exit
    try:
        client.images.get(image_name)
    except docker.errors.ImageNotFound as e1:
        click.echo(e1)
        sys.exit(1)
    except docker.errors.APIError as e2:
        click.echo(e2)
        sys.exit(2)

    # Get query from parameters/options
    if query_string:
        query = query_string
    elif query_file:
        if not os.path.isfile(query_file):
            click.echo("Input file does not exist")
            sys.exit(1)
        with open(query_file, "r") as ifile:
            query = ifile.read()
    else:
        click.echo("You must specify a query either through " +
                    "the -q option or by passing the path to a " +
                    "file containing a sql query (see directory queries). " +
                    "Run again with --help for usage.")
        return
    # Build command string list
    command = ["-U", "sa", "-P", password,
               "-S", ",".join([host, "1433"]),
               "-Q", query]
    if prune:
        command.extend(["-W", "-s", ",", "-m", "1"])
    # Run container
    try:
        container = client.containers.run(image = image_name,
                                          network_mode = "host",
                                          command = command,
                                          detach = True)
        # Container logs
        response_iterator = container.logs(stdout = True,
                                           stream = True,
                                           timestamps = False,
                                           tail = False)
        # Iterate through stream of logs
        if output_file:
            to = 'file'
        else:
            to = 'stdout'
        printStream(response_iterator, to, output_file)

        # Kill and remove container
        container.stop()
        container.remove()

    # Exceptions
    except docker.errors.APIError as e:
        click.echo(e)
    except docker.errors.ContainerError as e2:
        click.echo(e2)

    # If written to file and prune is enabled, remove second line using awk
    if prune and output_file:
        os.system("sed -i '2d' {}".format(output_file))


# Helper function
def printStream(iterator, to = 'stdout', filename = 'tmp.csv'):
    if to == 'stdout':
        out = sys.stdout
    elif to == 'stderr':
        out = sys.stderr
    elif to == 'file':
        out = open(filename, 'w')
    # Iterate stream of text/data
    try:
        while True:
            out.write(next(iterator))
            out.flush()
    except StopIteration:
        pass
    finally:
        del iterator
        if to == 'file':
            out.close()

if __name__ == "__main__":
    sqlcmd()
