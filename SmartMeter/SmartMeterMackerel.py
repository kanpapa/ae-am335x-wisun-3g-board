#!/usr/bin/env python
# -*- coding: utf-8 -*-

# SmartMeterMackerel.py
# for the Akizuki SoC board and Mackerel  https://mackerel.io
#
# This program is a modified version of SmartMeter.py from the reference site.
# https://qiita.com/kanon700/items/d4df13d45c2a9d16b8b0.
#
# This program used the Mackerel API Client for Python.
# https://github.com/cm-watanabeseigo/mackerel-api-client-python

from time import sleep, gmtime, time
from makapi import makapi

import sys
import serial
import configparser
import time
import json
import datetime

# Mackerel APIKEY
m = makapi("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

# シリアルポートデバイス名
#serialPortDev = 'COM5'  # Windows の場合
serialPortDev = '/dev/ttyS1'  # Linuxの場合

# 瞬時電力計測値取得コマンドフレーム
echonetLiteFrame = b'\x10\x81\x00\x01\x05\xFF\x01\x02\x88\x01\x62\x01\xE7\x00'

# 設定情報読み出し
inifile       = configparser.ConfigParser()
inifile.read('./SmartMeter.ini', 'utf-8')
Broute_id     = inifile.get('settings', 'broute_id')
Broute_pw     = inifile.get('settings', 'broute_pw')
Channel       = inifile.get('settings', 'channel')
PanId         = inifile.get('settings', 'panid')
Address       = inifile.get('settings', 'address')

# シリアルポート初期化
ser = serial.Serial(serialPortDev, 115200) # シリアルポートオープン
ser.timeout = 2 # シリアル通信のタイムアウトを設定

# Bルート認証パスワード設定
print('Bルートパスワード設定')
ser.write(str.encode("SKSETPWD C " + Broute_pw + "\r\n"))
ser.readline() # エコーバック
print(ser.readline().decode(encoding='utf-8'), end="")  # 成功ならOKを返す

# Bルート認証ID設定
print('Bルート認証ID設定')
ser.write(str.encode("SKSETRBID " + Broute_id + "\r\n"))
ser.readline() # エコーバック
print(ser.readline().decode(encoding='utf-8'), end="") # 成功ならOKを返す

# Channel設定
print('Channel設定')
ser.write(str.encode("SKSREG S2 " + Channel + "\r\n"))
ser.readline()  # エコーバック
print(ser.readline().decode(encoding='utf-8'), end="")  # 成功ならOKを返す

# PanID設定
print('PanID設定')
ser.write(str.encode("SKSREG S3 " + PanId + "\r\n"))
ser.readline() # エコーバック
print(ser.readline().decode(encoding='utf-8'), end="") # 成功ならOKを返す

# PANA 接続シーケンス
print('PANA接続シーケンス')
ser.write(str.encode("SKJOIN " + Address + "\r\n"))
ser.readline()  # エコーバック
print(ser.readline().decode(encoding='utf-8'), end="") # 成功ならOKを返す

# PANA 接続完了待ち
bConnected = False
while not bConnected :
    line = ser.readline().decode(encoding='utf-8')
    if line.startswith("EVENT 24") :
        print("PANA 接続失敗")
        sys.exit() #接続失敗した時は終了
    elif line.startswith("EVENT 25") :
        print('PANA 接続成功')
        bConnected = True

ser.readline() #インスタンスリストダミーリード

while True:
    # コマンド送信
    command = "SKSENDTO 1 {0} 0E1A 1 0 {1:04X} ".format(Address, len(echonetLiteFrame))
    ser.write(str.encode(command) + echonetLiteFrame)
    
    # OKがくるまで読み飛ばす
    bConnected = False
    while not bConnected :
        Data = ser.readline().decode(encoding='utf-8')
        print(Data)
        if Data.startswith("OK") :
            bConnected = True

    time.sleep(1)

    # 返信データ取得
    Data = ser.readline().decode(encoding='utf-8')
    print(Data)

    # データチェック
    if Data.startswith("ERXUDP"):
        cols = Data.strip().split(' ')
        res = cols[9]   # UDP受信データ部分
        seoj = res[8:8+6]
        ESV = res[20:20+2]
        # スマートメーター(028801)から来た応答(72)なら
        if seoj == "028801" and ESV == "72" :
            EPC = res[24:24 + 2]

            # 瞬時電力計測値(E7)なら
            if EPC == "E7" :
                hexPower = Data[-8:] # 最後の4バイトが瞬時電力計測値
                intPower = int(hexPower, 16)
                print(u"瞬時電力計測値:{0}[W]".format(intPower))
                
                # Mackerel API
                intTime = int(time.time())
                ret = m.post('tsdb','[{"hostId":"XXXXXXXX","name":"power","time":' + str(intTime) + ',"value":' + str(intPower) + '}]')
                print(json.dumps(ret, separators=(',', ':')))

    # logging time
    dt_now = datetime.datetime.now()
    print(dt_now)

    # 1分毎に取得する
    sleep(60)

# ガード処理
ser.close()

