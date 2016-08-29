#!/bin/bash
for item in $(ls -1 *work*.tif); do rm -f $item".zip"; zip $item".zip" $item; done

