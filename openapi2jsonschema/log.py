#!/usr/bin/env python

import click


def info(message):
    click.echo(click.style(message, fg="green"))


def debug(message):
    click.echo(click.style(message, fg="yellow"))


def error(message):
    click.echo(click.style(message, fg="red"))
