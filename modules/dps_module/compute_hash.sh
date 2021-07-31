#!/bin/sh

sha256sum /psma/collected_data/* > /psma/result
zip /psma/result /psma/result
rm /psma/result
