#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractclassmethod
import time
from time import sleep
import threading
import Command
import Keys
import cv2
from Keys import Button, Direction, Stick
import tkinter.simpledialog as simpledialog
import tkinter as tk

# the class For notifying stop signal is sent from Main window
class StopThread(Exception):
	pass

# Python command
class PythonCommand(Command.Command):
	def __init__(self, name):
		super(PythonCommand, self).__init__(name)
		#print('init Python command: ' + name)
		self.keys = None
		self.thread = None
		self.alive = True
		self.postProcess = None

	@abstractclassmethod
	def do(self):
		pass

	def do_safe(self, ser):
		if self.keys is None:
			self.keys = Keys.KeyPress(ser)

		try:
			if self.alive:
				self.do()
				self.finish()
		except StopThread:
			print(self.name + ' has finished successfully.')
		except:
			if self.keys is None:
				self.keys = Keys.KeyPress(ser)
			print('interruppt')
			import traceback
			traceback.print_exc()
			self.keys.end()
			self.alive = False

	def start(self, ser, postProcess=None):
		self.alive = True
		self.postProcess = postProcess
		if not self.thread:
			self.thread = threading.Thread(target=self.do_safe, args=(ser,))
			self.thread.start()

	def end(self, ser):
		self.sendStopRequest()

	def sendStopRequest(self):
		if self.checkIfAlive(): # try if we can stop now
			self.alive = False
			print(self.name + ': we\'ve sent a stop request.')

	# NOTE: Use this function if you want to get out from a command loop by yourself
	def finish(self):
		self.alive = False
		self.end(self.keys.ser)

	# press button at duration times(s)
	def press(self, buttons, duration=0.1, wait=0.1):
		self.keys.input(buttons)
		self.wait(duration)
		self.keys.inputEnd(buttons)
		self.wait(wait)
		self.checkIfAlive()

	# press button at duration times(s) repeatedly
	def pressRep(self, buttons, repeat, duration=0.1, interval=0.1, wait=0.1):
		for i in range(0, repeat):
			self.press(buttons, duration, 0 if i == repeat - 1 else interval)
		self.wait(wait)

	# add hold buttons
	def hold(self, buttons):
		self.keys.hold(buttons)

	# release holding buttons
	def holdEnd(self, buttons):
		self.keys.holdEnd(buttons)
		self.checkIfAlive()

	# do nothing at wait time(s)
	def wait(self, wait):
		sleep(wait)
		self.checkIfAlive()

	def checkIfAlive(self):
		if not self.alive:
			self.keys.end()
			self.keys = None
			self.thread = None

			if not self.postProcess is None:
				self.postProcess()
				self.postProcess = None

			# raise exception for exit working thread
			raise StopThread('exit successfully')
		else:
			return True

# Python command using rank match glitch
class RankGlitchPythonCommand(PythonCommand):
	def __init__(self, name):
		super(RankGlitchPythonCommand, self).__init__(name)
		self.day = 0

	# Use time glitch
	# Controls the system time and get every-other-day bonus without any punishments
	def timeLeap(self, is_go_back=True):
		self.press(Button.HOME, wait=1)
		self.press(Direction.DOWN)
		self.press(Direction.RIGHT)
		self.press(Direction.RIGHT)
		self.press(Direction.RIGHT)
		self.press(Direction.RIGHT)
		self.press(Button.A, wait=1.5)  # System Settings
		self.press(Direction.DOWN, duration=2, wait=0.5)

		self.press(Button.A, wait=0.3)  # System Settings > System
		self.press(Direction.DOWN)
		self.press(Direction.DOWN)
		self.press(Direction.DOWN)
		self.press(Direction.DOWN, wait=0.3)
		self.press(Button.A, wait=0.2)  # Date and Time
		self.press(Direction.DOWN, duration=0.7, wait=0.2)

		# increment and decrement
		if is_go_back:
			self.press(Button.A, wait=0.2)
			self.press(Direction.UP, wait=0.2)  # Increment a year
			# self.press(Direction.RIGHT, duration=1.5)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, wait=0.5)

			self.press(Direction.UP, wait=0.1)
			self.press(Direction.UP, wait=0.1)
			self.press(Button.A, wait=0.2)
			self.press(Button.A, wait=0.2)
		# self.press(Button.A, wait=0.2)
		# self.press(Direction.LEFT, duration=1.5)
		# self.press(Direction.DOWN, wait=0.2)  # Decrement a year
		# self.press(Direction.RIGHT, duration=1.5)
		# self.press(Button.A, wait=0.5)

		# use only increment
		# for use of faster time leap
		else:
			self.press(Button.A, wait=0.2)
			self.press(Direction.RIGHT)
			self.press(Direction.RIGHT)
			self.press(Direction.UP, wait=0.2)  # increment a day
			# self.press(Direction.RIGHT, duration=1)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, duration=0.05, wait=0.03)
			self.press(Button.A, wait=0.5)

		self.press(Button.HOME, wait=1)
		self.press(Button.HOME, wait=1)


TEMPLATE_PATH = "./Template/"


class ImageProcPythonCommand(PythonCommand):
	def __init__(self, name, cam):
		super(ImageProcPythonCommand, self).__init__(name)
		self.camera = cam

	# Judge if current screenshot contains an image using template matching
	# It's recommended that you use gray_scale option unless the template color wouldn't be cared for performace
	# 現在のスクリーンショットと指定した画像のテンプレートマッチングを行います
	# 色の違いを考慮しないのであればパフォーマンスの点からuse_grayをTrueにしてグレースケール画像を使うことを推奨します
	def isContainTemplate(self, template_path, threshold=0.7, use_gray=True, show_value=False):
		src = self.camera.readFrame()
		src = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY) if use_gray else src

		template = cv2.imread(TEMPLATE_PATH + template_path, cv2.IMREAD_GRAYSCALE if use_gray else cv2.IMREAD_COLOR)
		w, h = template.shape[1], template.shape[0]

		method = cv2.TM_CCOEFF_NORMED
		res = cv2.matchTemplate(src, template, method)
		_, max_val, _, max_loc = cv2.minMaxLoc(res)

		if show_value:
			print(template_path + ' ZNCC value: ' + str(max_val))

		if max_val > threshold:
			if use_gray:
				src = cv2.cvtColor(src, cv2.COLOR_GRAY2BGR)

			top_left = max_loc
			bottom_right = (top_left[0] + w, top_left[1] + h)
			cv2.rectangle(src, top_left, bottom_right, (255, 0, 255), 2)
			return True
		else:
			return False

	# Get interframe difference binarized image
	# フレーム間差分により2値化された画像を取得
	def getInterframeDiff(self, frame1, frame2, frame3, threshold):
		diff1 = cv2.absdiff(frame1, frame2)
		diff2 = cv2.absdiff(frame2, frame3)

		diff = cv2.bitwise_and(diff1, diff2)

		# binarize
		img_th = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)[1]

		# remove noise
		mask = cv2.medianBlur(img_th, 3)
		return mask

	def loopwhileImage(self, src, s=60):
		print('Image recognition:{}'.format(src), end="")
		tcount = 0.0
		while not self.isContainTemplate(src, 0.7):
			tcount += 0.25
			self.wait(0.25)
			if tcount > s:
				print('Something wrong :{}'.format(src))  # force finish
				self.finish()
				return False
		print('  ...Found!')
		return True


# Sync as controller
# 同期
class Sync(PythonCommand):
	def __init__(self, name):
		super(Sync, self).__init__(name)

	def do(self):
		self.wait(1)

		self.press(Button.A, 0.1, 2)
		self.press(Button.HOME, 0.1, 1)
		self.press(Button.A, 0.1, 0.5)


# Unsync controller
# 同期解除
class Unsync(PythonCommand):
	def __init__(self, name):
		super(Unsync, self).__init__(name)

	def do(self):
		self.wait(1)
		self.press(Button.HOME, 0.1, 0.5)
		self.press(Direction.DOWN, 0.1, 0.1)
		self.press(Direction.RIGHT, 0.1, 0.1)
		self.press(Direction.RIGHT, 0.1, 0.1)
		self.press(Direction.RIGHT, 0.1, 0.1)
		self.press(Button.A, 0.1, 1.5)
		self.press(Button.A, 0.1, 0.5)
		self.press(Button.A, 0.1, 0.3)


# Mash a button A
# A連打
class Mash_A(PythonCommand):
	def __init__(self, name):
		super(Mash_A, self).__init__(name)

	def do(self):
		while True:
			self.wait(0.5)
			self.press(Button.A)


# Auto league
# 自動リーグ周回(画像認識なし)
class AutoLeague(PythonCommand):
	def __init__(self, name):
		super(AutoLeague, self).__init__(name)

	def do(self):
		self.hold(Direction(Stick.LEFT, 70))
		while True:
			self.wait(0.5)

			for _ in range(0, 10):
				self.press(Button.A, wait=0.5)

			self.press(Button.B)


# Auto league IP
# 自動リーグ周回(画像認識あり)
class AutoLeagueIP(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(AutoLeagueIP, self).__init__(name, cam)

	def do(self):
		while self.checkIfAlive():

			self.wait(0.5)
			if self.isContainTemplate(
					'League/fight.png'):  # or self.isContainTemplate('waza_setsumei.png', 0.8):  # たたかう
				print('Fight')
				self.press(Button.A, wait=1.5)
				if self.isContainTemplate('League/daimax.png', 0.6):  # and not self.isContainTemplate(
					# 'not_affected.png'):　先頭はダイマックス
					print('Daimax!')
					self.press(Direction.LEFT, wait=0.75)
					self.press(Button.A, wait=0.75)
					self.press(Button.A, wait=0.75)
				else:
					self.press(Button.A, wait=0.7)
			elif self.isContainTemplate("League/Fainted.png", 0.9):
				print('瀕死')
				self.press(Direction.DOWN, wait=1)
				while self.isContainTemplate('League/Fainted.png', 0.9):  # 瀕死が2体以上居たとき用
					self.press(Direction.DOWN, wait=1)
					self.press(Button.B, wait=1)
				self.press(Button.A, wait=1)
				self.press(Button.A, wait=1)
				self.press(Button.B, wait=1)
			elif self.isContainTemplate('League/Tournament_next_battle.png', 0.95):  # 勝利時つぎにすすむ
				self.press(Direction.UP, duration=4)
			elif self.isContainTemplate('League/Network_Offline.png', 0.8):  # Tournamentを始める
				self.press(Direction(Stick.LEFT, 90), duration=5)
				self.press(Button.A, wait=1)
				self.press(Button.A, wait=1)
				self.press(Button.A, wait=1)
				self.press(Button.B, wait=1)
				self.press(Button.B, wait=1)
				self.press(Button.B, wait=1)
			else:  # 基本はAボタン
				self.press(Button.A, wait=1.0)
			if not self.checkIfAlive(): return


# using Rank Battle glitch
# Infinity ID lottery
# 無限IDくじ(ランクマッチ使用)
class InfinityLottery(RankGlitchPythonCommand):
	def __init__(self, name):
		super(InfinityLottery, self).__init__(name)

	def do(self):
		while True:
			self.press(Button.A, wait=0.5)
			self.press(Button.B, wait=0.5)
			self.press(Direction.DOWN, wait=0.5)

			for _ in range(0, 10):  # A loop
				self.press(Button.A, wait=0.5)

			for _ in range(0, 20):  # B loop
				self.press(Button.B, wait=0.5)

			# Time glitch
			self.timeLeap()


# using RankBattle glitch
# Infinity getting berries
# 無限きのみ(ランクマッチ, 画像認識任意)
class InfinityBerry(ImageProcPythonCommand, RankGlitchPythonCommand):
	def __init__(self, name, cam):
		super(InfinityBerry, self).__init__(name, cam)
		self.cam = cam

	def do(self):
		while True:

			# If camera is not opened, then pick 1 and timeleap
			if not self.cam.isOpened():
				self.press(Button.A, wait=0.5)
				self.press(Button.B, wait=0.5)
				self.press(Button.A, wait=0.5)  # yes

				for _ in range(0, 15):  # B loop
					self.press(Button.B, wait=0.5)

				# Time glitch
				self.timeLeap()

			else:
				self.press(Button.A, wait=0.5)
				self.press(Button.B, wait=0.5)
				self.press(Button.A, wait=0.5)  # yes

				while True:
					self.press(Button.A, wait=0.5)  # for press 'shake more'
					self.press(Button.A, wait=0.5)  # just in case
					self.press(Button.A, wait=0.5)

					while not self.isContainTemplate('fell_message.png'):
						self.press(Button.B, wait=0.5)
					print('fell message!')
					self.press(Button.A, wait=0.5)

					# Judge continuity by tree shaking motion
					if self.isContinue():
						print('continue')
						self.wait(0.5)
						continue
					else:
						print('not continue')
						break

				for _ in range(0, 10):  # B loop
					self.press(Button.B, wait=0.5)

				# Time glitch
				self.timeLeap()

	def isContinue(self, check_interval=0.1, check_duration=2):
		time = 0
		zero_cnt = 0
		height_half = int(self.camera.capture_size[1] / 2)

		frame1 = cv2.cvtColor(self.camera.readFrame()[0:height_half - 1, :], cv2.COLOR_BGR2GRAY)
		sleep(check_interval / 3)
		frame2 = cv2.cvtColor(self.camera.readFrame()[0:height_half - 1, :], cv2.COLOR_BGR2GRAY)
		sleep(check_interval / 3)
		frame3 = cv2.cvtColor(self.camera.readFrame()[0:height_half - 1, :], cv2.COLOR_BGR2GRAY)

		while time < check_duration:
			mask = self.getInterframeDiff(frame1, frame2, frame3, 15)
			zero_cnt += cv2.countNonZero(mask)

			frame1 = frame2
			frame2 = frame3
			sleep(check_interval)
			frame3 = cv2.cvtColor(self.camera.readFrame()[0:height_half - 1, :], cv2.COLOR_BGR2GRAY)

			time += check_interval

		print('diff cnt: ' + str(zero_cnt))

		# zero count threshold is heuristic value... weather: sunny
		return True if zero_cnt < 9000 else False


# using RankBattle glitch
# Auto cafe battles
# 無限カフェ(ランクマッチ使用)
class InfinityCafe(ImageProcPythonCommand, RankGlitchPythonCommand):
	def __init__(self, name, cam):
		super(InfinityCafe, self).__init__(name, cam)
		self.pp_max = 10

	def do(self):
		while True:
			# battle agaist a master at PP times
			for __ in range(0, self.pp_max):
				self.wait(1)

				while not self.isContainTemplate("fight.png", 0.7):
					self.press(Button.A, wait=0.5)
				while not self.isContainTemplate("Network_Offline.png", 0.8):
					self.press(Button.A, wait=2.0)
				#
				# for _ in range(0, 35):	# A loop
				# 	self.press(Button.A, wait=0.5)
				# self.wait(5)
				#
				# for _ in range(0, 45):  # B loop
				# 	self.press(Button.B, wait=0.5)

				self.timeLeap()

			# go to pokemon center to restore PP
			self.press(Direction.DOWN, duration=3.5)
			self.press(Button.X, wait=1)
			self.press(Button.A, wait=3)  # open up a map
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=4)
			self.press(Direction.UP, duration=0.2)
			self.press(Direction.UP_LEFT, duration=1, wait=2)

			# in pokemon center
			self.press(Direction.UP, duration=2)
			for _ in range(0, 10):  # A loop
				self.press(Button.A, wait=0.5)
			for _ in range(0, 25):  # B loop
				self.press(Button.B, wait=0.5)
			self.press(Direction.DOWN, duration=2, wait=2)

			# move to cafe in Wyndon (Shoot City)
			self.press(Direction.LEFT, duration=3)
			self.press(Direction.UP, duration=4)
			self.press(Direction.RIGHT, duration=1, wait=2)

			self.press(Direction.UP, duration=2, wait=1)


# auto releaseing pokemons
class AutoRelease(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(AutoRelease, self).__init__(name, cam)
		self.row = 5
		self.col = 6
		self.cam = cam

	def do(self):
		self.wait(0.5)

		for i in range(0, self.row):
			for j in range(0, self.col):
				if not self.cam.isOpened():
					self.Release()
				else:
					# if shiny, then skip
					if not self.isContainTemplate('shiny_mark.png', threshold=0.9):
						if self.isContainTemplate('status.png',
												  threshold=0.7):  # Maybe this threshold works for only Japanese version.
							# Release a pokemon
							self.Release()

				if not j == self.col - 1:
					if i % 2 == 0:
						self.press(Direction.RIGHT, wait=0.2)
					else:
						self.press(Direction.LEFT, wait=0.2)

			self.press(Direction.DOWN, wait=0.2)

		# Return from pokemon box
		self.press(Button.B, wait=2)
		self.press(Button.B, wait=2)
		self.press(Button.B, wait=1.5)

	def Release(self):
		self.press(Button.A, wait=0.2)  # *をどうしますか？
		self.press(Direction.UP)  # ↑
		self.press(Direction.UP)  # ↑
		self.press(Button.A, wait=1)  # にがす
		self.press(Direction.UP)  # ↑
		self.press(Button.A, wait=1.45)  # はい
		self.press(Button.A, wait=0.2)


# Egg hatching at count times
# 指定回数の孵化(キャプボあり)
class CountHatching(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(CountHatching, self).__init__(name, cam)
		self.hatched_num = 0
		self.count = 5
		self.place = 'wild_area'

	def do(self):
		start_time = time.time()
		while self.hatched_num < self.count:
			if self.hatched_num == 0:
				self.press(Direction.RIGHT, duration=1)

			self.hold([Direction.RIGHT, Direction.R_LEFT])

			# turn round and round
			while not self.isContainTemplate('egg_notice.png'):
				self.wait(1)

			print('egg hatching')
			self.holdEnd([Direction.RIGHT, Direction.R_LEFT])
			self.press(Button.A)
			self.wait(15)
			for i in range(0, 5):
				self.press(Button.A, wait=1)
			tm = round(time.time() - start_time, 2)
			self.hatched_num += 1
			print('Elapsed time: {}\nAverage : {}'.format(tm, tm / self.hatched_num))
			print('hatched_num: ' + str(self.hatched_num))


# auto egg hatching using image recognition
# 自動卵孵化(キャプボあり)
class AutoHatching(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(AutoHatching, self).__init__(name, cam)
		self.cam = cam
		self.party_num = 1  # don't count eggs
		self.party_egg_num = 0  # eggs count in party
		self.hatched_num = 0
		self.hatched_box_num = 0
		self.itr_max = 6
		self.egg_spawn_time = 300  # sec
		self.is_hatching = False

	def do(self):
		initial_time = time.time()
		self.press(Direction.DOWN, duration=0.05, wait=0.5)
		self.press(Direction.DOWN, duration=0.8)
		self.press(Direction.LEFT, duration=0.2)

		while True:
			for i in range(0, self.itr_max):
				print('iteration: ' + str(i + 1) + ' (' + str(i * 5) + '/30) -> (' + str((i + 1) * 5) + '/30)')
				print('hatched box num : ' + str(self.hatched_box_num))

				if self.getNewEgg():
					self.party_egg_num += 1
				self.press(Direction.UP, duration=0.05, wait=0.5)
				self.press(Direction.UP_RIGHT, duration=1)

				# hatch eggs
				while self.party_num < 6:
					start_time = time.time()
					self.press(Direction.RIGHT, duration=1)
					self.hold([Direction.RIGHT, Direction.R_LEFT])

					# turn round and round
					while not self.isContainTemplate('egg_notice.png'):
						self.wait(1)
						if not (self.party_num == 0 or self.party_num == 5) \
								and time.time() - start_time > self.egg_spawn_time:
							break

					self.holdEnd([Direction.RIGHT, Direction.R_LEFT])
					if self.hatched_num == 0:
						self.egg_spawn_time = int((time.time() - start_time) / 1.8)

					if self.isContainTemplate('egg_notice.png') or self.isContainTemplate('dialogue.png', 0.85):
						self.hatched_num += 1

						self.party_egg_num -= 1
						self.party_num += 1

						self.is_hatching = True
						# self.egg_spawn_time -= 3
						print('egg hatching')
						self.press(Button.A)
						self.wait(15)
						while not self.isContainTemplate('Network_Offline.png'):
							self.press(Button.A, wait=1)
						print('party_num: ' + str(self.party_num) + ', party_egg_num: ' + str(self.party_egg_num))
						print('all hatched num: ' + str(self.hatched_num))
						print('Elapsed time: ' + str(round(time.time() - initial_time, 2)))
						print('Average time per egg: ' + str(round((time.time() - initial_time) / self.hatched_num, 2)))
					else:
						self.is_hatching = False
						# self.egg_spawn_time += 6
						print('next egg.')

					self.press(Button.X, wait=1)
					self.press(Button.A, wait=3)  # open up a map
					self.press(Button.A, wait=1)
					self.press(Button.A, wait=4)
					self.press(Direction.DOWN, duration=0.05, wait=0.5)
					self.press(Direction.DOWN, duration=0.8)
					self.press(Direction.LEFT, duration=0.2)

					# if self.party_num < 6:  # 手持ちが6体未満なら
					#     # get a new egg
					#     self.getNewEgg()
					#     self.press(Direction.UP, duration=0.05, wait=0.5)
					#     self.press(Direction.UP, duration=1)

					if self.party_num + self.party_egg_num < 6:  # 手持ちがいっぱいでないなら
						# get a new egg
						if self.getNewEgg():
							self.party_egg_num += 1
						self.press(Direction.UP, duration=0.05, wait=0.5)
						self.press(Direction.UP_RIGHT, duration=1)

				# open up pokemon box
				self.press(Button.X, wait=1)
				self.press(Direction.UP, wait=0.5)  # set cursor to party
				self.press(Button.A, wait=2)
				self.press(Button.R, wait=2)

				self.putPokemonsToBox(start=1, num=5)
				self.party_num = 1

				if i < self.itr_max - 1:
					self.press(Button.B, wait=0.5)
					self.press(Button.B, wait=2)
					self.press(Button.B, wait=2)
					self.press(Direction.DOWN, wait=0.2)  # set cursor to map
					self.press(Button.B, wait=1.5)

			self.hatched_box_num += 1

			# release
			self.press(Button.B, wait=0.8)
			self.press(Button.Y, wait=0.2)
			self.press(Direction.DOWN, wait=0.3)
			self.press(Direction.DOWN, wait=0.3)

			# As of now, stop if shiny is in box
			is_contain_shiny = self.ReleaseBox()
			if is_contain_shiny:
				print('shiny!')
				break

			self.press(Button.B, wait=0.5)
			self.press(Button.B, wait=2)
			self.press(Button.B, wait=2)
			self.press(Direction.DOWN, wait=0.2)  # set cursor to map
			self.press(Button.B, wait=1.5)

	def getNewEgg(self):
		egg_found = False
		self.press(Button.A, wait=0.5)
		if not self.isContainTemplate('egg_found.png'):
			print('egg not found')
			self.press(Button.B, wait=1)
			self.press(Button.B, wait=1)
			self.press(Button.B, wait=1)
		# self.finish()  # TODO
		else:
			print('egg found')
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=3)
			self.press(Button.A, wait=2)
			self.press(Button.A, wait=2)
			self.press(Button.A, wait=1)
			egg_found = True
		return egg_found

	def putPokemonsToBox(self, start=0, num=1):
		self.press(Direction.LEFT, wait=0.3)
		self.pressRep(Direction.DOWN, start, wait=0.3)

		# select by range
		self.press(Button.Y, wait=0.2)
		self.press(Button.Y, wait=0.2)
		self.press(Button.A, wait=0.2)
		self.pressRep(Direction.DOWN, num - 1)
		self.press(Button.A, wait=0.2)

		# put to box
		self.pressRep(Direction.UP, 3)
		self.press(Direction.RIGHT, wait=0.2)
		self.press(Button.A, wait=0.5)
		self.press(Button.A, wait=0.5)

	def ReleaseBox(self):
		row = 5
		col = 6
		for i in range(0, row):
			for j in range(0, col):

				# if shiny, then stop
				if self.isContainTemplate('shiny_mark.png', threshold=0.9):
					return True

				# Maybe this threshold works for only Japanese version.
				if self.isContainTemplate('status.png', threshold=0.7):
					# Release a pokemon
					self.Release()

				if not j == col - 1:
					if i % 2 == 0:
						self.press(Direction.RIGHT, wait=0.2)
					else:
						self.press(Direction.LEFT, wait=0.2)

			self.press(Direction.DOWN, wait=0.2)

		return False

	def Release(self):
		self.press(Button.A, wait=0.2)  # *をどうしますか？
		self.press(Direction.UP)  # ↑
		self.press(Direction.UP)  # ↑
		self.press(Button.A, wait=1)  # にがす
		self.press(Direction.UP)  # ↑
		self.press(Button.A, wait=1.45)  # はい
		self.press(Button.A, wait=0.2)


# for debug
class Debug(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(Debug, self).__init__(name, cam)

	def do(self):
		self.goRound()

	def goRound(self):
		self.press(Direction.LEFT, duration=0.5)
		self.press(Direction.DOWN_LEFT, duration=0.5)
		self.press(Direction.DOWN, duration=0.5)
		self.press(Direction.DOWN_RIGHT, duration=0.5)
		self.press(Direction.RIGHT, duration=0.5)
		self.press(Direction.UP_RIGHT, duration=0.5)
		self.press(Direction.UP, duration=0.5)
		self.press(Direction.UP_LEFT, duration=0.5)


# Get watt automatically using the glitch
# source: MCU Command 'Infinity-Watt'
class InfinityWatt(RankGlitchPythonCommand):
	def __init__(self, name, is_use_rank=True):
		super(InfinityWatt, self).__init__(name)
		self.use_rank = is_use_rank

	def do(self):
		# n = int(input('Loop number'))
		n = MyDialog.input_value(self, "Loop number")
		i = 0
		while True:
			i += 1
			if n != 0 and i >= n:
				self.finish()
			print('------------Loop : ', i)
			self.wait(1)

			if self.use_rank:
				self.timeLeap()

				self.press(Button.A, wait=1)
				self.press(Button.A, wait=1)  # 2000W
				self.press(Button.A, wait=1.8)
				self.press(Button.B, wait=1.5)

			else:
				self.press(Button.A, wait=1)
				self.press(Button.A, wait=3)  # レイド開始

				self.press(Button.HOME, wait=1)
				self.press(Direction.DOWN)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Button.A, wait=1.5)  # 設定選択
				self.press(Direction.DOWN, duration=2, wait=0.5)

				self.press(Button.A, wait=0.3)  # 設定 > 本体
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Direction.DOWN, wait=0.3)
				self.press(Button.A, wait=0.2)  # 日付と時刻 選択
				self.press(Button.A, wait=0.4)

				self.press(Direction.DOWN, wait=0.2)
				self.press(Direction.DOWN, wait=0.2)
				self.press(Button.A, wait=0.2)
				self.press(Direction.UP, wait=0.2)
				self.press(Direction.RIGHT, duration=1, wait=0.3)
				self.press(Button.A, wait=0.5)
				self.press(Button.HOME, wait=1)  # ゲームに戻る
				self.press(Button.HOME, wait=2)

				self.press(Button.B, wait=1)
				self.press(Button.A, wait=6)  # レイドをやめる

				self.press(Button.A, wait=1)
				self.press(Button.A, wait=1)  # 2000W
				self.press(Button.A, wait=1.8)
				self.press(Button.B, wait=1.5)

				self.press(Button.HOME, wait=1)
				self.press(Direction.DOWN)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Button.A, wait=1.5)  # 設定選択
				self.press(Direction.DOWN, duration=2, wait=0.5)

				self.press(Button.A, wait=0.3)  # 設定 > 本体
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Button.A)  # 日付と時刻 選択
				self.press(Button.A, wait=0.5)

				self.press(Button.HOME, wait=1)  # ゲームに戻る
				self.press(Button.HOME, wait=1)



class HoldTest(PythonCommand):
	def __init__(self, name):
		super(HoldTest, self).__init__(name)

	def do(self):
		self.wait(1)

		while self.checkIfAlive():
			self.hold([Direction.LEFT, Direction.DOWN])
			self.wait(0.5)
			self.press(Button.X, wait=2)
			self.holdEnd([Direction.LEFT, Direction.DOWN])

			self.wait(1)

			self.hold(Direction.UP)
			self.wait(2)

			self.holdEnd(Direction.UP)
			self.wait(2)


class Hatch(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(Hatch, self).__init__(name, cam)

	def round_move(self):
		self.press([Direction('Stick.LEFT', 315), Direction('Stick.RIGHT', 135)],
				   duration=68.5)  # ポケ徹のサイクル:duration ≒ 35:68.5(=1:)

	def do(self):
		self.wait(1)
		while self.checkIfAlive():
			boxes = 6  # 連続する空ボックス
			self.wait(0)
			print("Now to Start {} boxes hatching!".format(boxes))
			start_time = time.time()
			for i in range(boxes):
				for j in range(0, 6):  # 5匹孵化×6個

					loops = 0
					for k in range(0, 5):  # 1セット(5体分)
						lap_start_time = time.time()
						print('{0}box {1}体目'.format(i + 1, 5 * j + k + 1))
						loops += 1
						# そらとぶタクシーで位置合わせ
						self.press(Button.X, wait=1.1)
						self.press(Button.A, wait=2.5)
						self.press(Button.A, wait=0.6)
						self.press(Button.A, wait=5.1)
						if not self.checkIfAlive(): return
						# たまごもらう
						self.press(Direction.DOWN, duration=0.7)
						self.press(Direction.RIGHT, duration=0.2, wait=0.6)
						self.press(Button.A, wait=0.6)  # キミのポケモンが…
						self.press(Button.A, wait=0.6)  # 欲しいですよね
						self.press(Direction.DOWN, wait=0.6)  # →いいえ(様子を見る)
						self.press(Direction.DOWN, wait=0.6)  # →はい(やめる)
						self.press(Button.A, wait=3.1)  # 選択
						self.press(Button.B, wait=2.6)  # 預け屋さんからタマゴをもらった
						self.press(Button.B, wait=1.6)  # 手持ちに加えました
						self.press(Button.B, wait=0.3)  # 大事に育ててね
						# ぐるぐるまわる

						self.press(Direction.UP, duration=0.3)
						self.press(Direction.RIGHT, duration=0.8)
						self.hold([Direction.RIGHT, Direction.R_LEFT])

						# turn round and round
						while not self.isContainTemplate('egg_notice.png'):
							self.wait(1)
							if not self.checkIfAlive(): return

						print('egg hatching')
						self.holdEnd([Direction.RIGHT, Direction.R_LEFT])
						# self.round_move()
						# 孵化中の待ち
						self.press(Button.A)
						self.wait(15)
						for i_ in range(0, 5):
							self.press(Button.A, wait=1)
						print('完了 : {0}秒経過(合計:{1}秒)'.format(round(time.time() - lap_start_time, 2),
															round(time.time() - start_time, 2)))

					# ぐるぐるまわる(残ってるタマゴ)
					# for lap in range(0, laps + 2):
					# self.round_move()
					# 孵化中の待ち
					for waiting in range(0, 18):
						self.press(Button.A)
						self.wait(1)
					print('5匹孵化完了 : {}秒経過'.format(round(time.time() - start_time, 2)))

					# ボックス贈り
					self.press(Button.X, wait=1)  # メニュー
					self.press(Direction.UP)  # ↑
					self.press(Button.A, wait=2)  # ポケモン
					self.press(Button.R, wait=2)  # ボックス
					self.press(Direction.LEFT)  # 先頭選択
					self.press(Direction.DOWN)  # タマゴ選択
					self.press(Button.Y)  # はんいモード切り替え
					self.press(Button.Y)
					self.press(Button.A)  # ここから
					self.press(Direction.UP)
					self.press(Direction.UP)
					self.press(Button.A)  # ここまで
					self.press(Direction.RIGHT)
					self.press(Direction.DOWN)
					self.press(Direction.DOWN)
					self.press(Direction.DOWN)
					self.press(Direction.DOWN)
					self.press(Button.A, wait=0.5)  # いちらん選択
					self.press(Button.A, wait=0.5)  # ボックスに置く
					self.press(Button.B, wait=0.2)  # もどる(ボックス)
					if j == 5:  # j==5 (ボックス1つ分終わったとき)右のボックスに遷移
						self.press(Button.R, wait=0.3)
					self.press(Button.B, wait=2)  # もどる(ポケモン)
					self.press(Button.B, wait=1.5)  # もどる(メニュー)
					self.press(Direction.DOWN)  # タウンマップ選択
					self.press(Button.B, wait=2)  # もどる
			print('FINISH in {} sec'.format(round(time.time() - start_time, 2)))
			self.finish()


class Release(PythonCommand):
	def __init__(self, name):
		super(Release, self).__init__(name)

	def do(self):
		self.wait(1)
		while self.checkIfAlive():
			for row in range(0, 5):
				for col in range(0, 6):
					self.press(Button.A, wait=0.2)  # *をどうしますか？
					self.press(Direction.UP)  # ↑
					self.press(Direction.UP)  # ↑
					self.press(Button.A, wait=1)  # にがす
					self.press(Direction.UP)  # ↑
					self.press(Button.A, wait=1.45)  # はい
					self.press(Button.A, wait=0.2)
					self.press(Direction.RIGHT, wait=0.2)  # 次へ

				self.press(Direction.RIGHT)
				self.press(Direction.DOWN)
			self.press(Direction.DOWN)
			self.press(Direction.DOWN)
			self.press(Button.R, wait=0.3)
			self.finish()


class Seedconsume(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(Seedconsume, self).__init__(name, cam)

	def change_day(self):
		self.press(Button.A, duration=0.05, wait=0.15)
		self.press(Direction.LEFT, duration=0.05, wait=0.05)
		self.press(Direction.LEFT, duration=0.05, wait=0.05)
		self.press(Direction.LEFT, duration=0.05, wait=0.01)
		self.press(Direction.UP, duration=0.05, wait=0.01)  # increment a day
		# self.press(Direction.RIGHT, wait=0.05)
		# self.press(Direction.RIGHT, wait=0.05)
		# self.press(Direction.RIGHT, wait=0.05)
		self.press(Button.A, duration=0.05, wait=0.05)
		self.press(Button.A, duration=0.05, wait=0.05)
		self.press(Button.A, duration=0.05, wait=0.05)
		self.press(Button.A, duration=0.05, wait=0.15)

	def do(self):
		self.wait(1)
		# loops = int(input("input how many loops"))
		loops = MyDialog.input_value(self, "Loops")
		print('Now to start {} loops for consuming seed'.format(loops))
		ndiv = loops // 30
		ndiv_ = loops - ndiv * 30
		print('LOOPS: ', loops)
		for i in range(ndiv):
			for j in range(30):
				print('Now : Frame {}'.format(i * 30 + j + 1))  # 1~31
				self.change_day()
				if not self.checkIfAlive(): return
			self.change_day()
			if not self.checkIfAlive(): return
		for k in range(ndiv_):
			print('Now : Frame {}'.format(ndiv * 30 + k + 1))
			self.change_day()
			if not self.checkIfAlive(): return

		self.finish()


class raid_search(ImageProcPythonCommand):  # ワット回収済みレイドの前から
	def __init__(self, name, cam):
		super(raid_search, self).__init__(name, cam)

	def do(self):
		searchfor = 'shandera.png'  # Silhouette
		print('Start searching {}'.format(searchfor))
		s = time.time()
		j = 1
		while self.checkIfAlive():
			self.wait(1)
			print('{}周目'.format(j), end="")
			for i in range(3):
				i += 1
				print('{}日目'.format(i))
				self.press(Button.A, wait=2.0)
				# self.loopwhileImage('minnade.png', 100)
				self.press(Button.A, wait=3)  # レイド開始

				self.press(Button.HOME, wait=1)
				self.press(Direction.DOWN)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Direction.RIGHT)
				self.press(Button.A, wait=1.5)  # 設定選択
				# self.press(Direction.DOWN, duration=2, wait=0.5)
				self.hold(Direction.DOWN)
				self.loopwhileImage('hontai.png', 100)
				self.holdEnd(Direction.DOWN)

				self.press(Button.A, wait=0.3)  # 設定 > 本体
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Direction.DOWN)
				self.press(Direction.DOWN, wait=0.3)
				self.press(Button.A, wait=0.3)  # 日付と時刻 選択
				# self.press(Button.A, wait=0.4)

				self.press(Direction.DOWN, wait=0.2)
				self.press(Direction.DOWN, wait=0.2)
				self.press(Button.A, wait=0.2)
				self.press(Direction.UP, wait=0.2)
				self.press(Direction.RIGHT, wait=0.1)
				self.press(Direction.RIGHT, wait=0.1)
				self.press(Direction.RIGHT, wait=0.1)
				self.press(Direction.RIGHT, wait=0.1)
				self.press(Direction.RIGHT, wait=0.1)
				self.press(Button.A, wait=0.5)
				self.press(Button.HOME, wait=1)  # ゲームに戻る
				self.press(Button.HOME, wait=2)

				self.press(Button.B, wait=1)
				self.press(Button.A)  # レイドをやめる
				self.loopwhileImage('Network_Offline.png', 100)
				self.wait(0.5)
				self.press(Button.A, wait=1.5)
				self.press(Button.A, wait=1.5)  # 2000W
				if not self.checkIfAlive(): return

			self.press(Button.A, wait=3)
			if self.isContainTemplate(searchfor, 0.8):
				print('found in {}.'.format(s - time.time()))
				self.finish()
			else:
				print('Not found.')
				self.press(Button.HOME, wait=0.6)  # EXIT Game
				self.press(Button.X, wait=0.6)
				self.press(Button.A, wait=2.5)  # closed
				j += 1
				if j % 10 == 0:
					self.press(Direction.DOWN)
					self.press(Direction.RIGHT)
					self.press(Direction.RIGHT)
					self.press(Direction.RIGHT)
					self.press(Direction.RIGHT)
					self.press(Button.A, wait=1.5)  # 設定選択
					# self.press(Direction.DOWN, duration=2, wait=0.5)
					self.hold(Direction.DOWN)
					t = 0
					self.loopwhileImage('hontai.png', 100)
					self.holdEnd(Direction.DOWN)

					self.press(Button.A, wait=0.3)  # 設定 > 本体
					self.press(Direction.DOWN)
					self.press(Direction.DOWN)
					self.press(Direction.DOWN)
					self.press(Direction.DOWN, wait=0.3)
					self.press(Button.A, wait=0.2)  # 日付と時刻 選択
					# self.press(Button.A, wait=0.4)

					self.press(Direction.DOWN, wait=0.2)
					self.press(Direction.DOWN, wait=0.2)
					self.press(Button.A, wait=0.2)
					self.press(Direction.DOWN, duration=6.5, wait=0.2)
					self.press(Direction.RIGHT, wait=0.1)
					self.press(Direction.RIGHT, wait=0.1)
					self.press(Direction.RIGHT, wait=0.1)
					self.press(Direction.RIGHT, wait=0.1)
					self.press(Direction.RIGHT, wait=0.1)
					self.press(Button.A, wait=0.5)
					self.press(Button.HOME, wait=1)  # ゲームに戻る
				self.press(Button.A, wait=2.0)  # Choose game
				# self.press(Button.A, wait=18.0)  # User selection
				self.press(Button.A)  # User selection
				self.loopwhileImage('OP.png', 500)
				self.press(Button.A, wait=7.0)  # load save-data


# レイド周回
class raid_loop(ImageProcPythonCommand):  # 周回するワット回収済みレイドの前、オフライン状態から
	def __init__(self, name, cam):
		super(raid_loop, self).__init__(name, cam)

	def do(self):
		print('Start loop')
		s = time.time()
		j = 1
		while True:
			self.wait(1)
			print('{}周目'.format(j), end="")
			self.loopwhileImage('Network_Offline.png', 10)
			self.press(Button.Y)  # YY-COMMUNICATION
			self.loopwhileImage('internet.png', 10)
			self.press(Button.PLUS, wait=10)  # Internet
			self.loopwhileImage('dialogue.png', 10)
			self.press(Button.B, wait=1)
			self.press(Button.B)  # back to wild-area
			self.loopwhileImage('Network_Online.png', 10)  # online check
			self.wait(0.5)
			self.press(Button.A, wait=5)  # open raid
			self.press(Button.A, wait=1)  # open raid
			self.loopwhileImage('change_pokemon.png', 10)  # timing check
			self.press(Direction.UP, wait=0.5)  # 準備完了
			self.press(Button.A, wait=0.5)  # 準備完了
			if self.isContainTemplate('start_battle.png'):
				t = 0
				while t < 160:  # wait for 180 sec
					t += 1
					if self.isContainTemplate('4check.png', 0.85):
						self.press(Button.A)  # start if there are 4 people checked
					elif self.isContainTemplate('fight.png'):  # In case Starting manually
						break
					else:
						self.wait(1.0)
			if not self.isContainTemplate("lonely.png", 0.9):
				for i in range(10):
					self.press(Button.A, wait=0.8)
				while not self.isContainTemplate('catch_or_not.png'):  # To quit game
					if self.isContainTemplate('fight.png') or self.isContainTemplate('cheers.png'):  # press A
						for i in range(8):
							self.press(Button.A, wait=0.5)
				j += 1
			self.press(Button.HOME, wait=2)  # EXIT Game
			self.press(Button.X, wait=0.6)
			self.press(Button.A, wait=2.5)  # closed
			self.press(Button.A, wait=1.0)  # Choose game
			self.press(Button.A)  # User selection
			self.loopwhileImage('OP.png', 30)  # recognize Opening
			self.press(Button.A, wait=7.0)  # load save-data
			print('{} s 経過'.format(time.time() - s))
# if not self.checkIfAlive(): return


# レイド周回
class three_day_raid_loop(ImageProcPythonCommand, RankGlitchPythonCommand):  # 周回するワット回収済みレイドの前、オフライン状態から
	def __init__(self, name, cam):
		super(three_day_raid_loop, self).__init__(name, cam)

	def do(self):
		print('Start loop')
		s = time.time()
		j = 1
		while True:
			self.wait(1)
			print('{}周目'.format(j), end="")
			for i in range(3):
				i += 1
				print('{}日目'.format(i))
				self.press(Button.A, wait=3.0)
				self.press(Button.A, wait=3.0)  # レイド開始

				self.timeLeap(False)

				self.press(Button.B, wait=1)
				self.press(Button.A)  # レイドをやめる
				while not self.isContainTemplate('Network_Offline.png', 0.8):
					self.wait(0.5)
				self.wait(0.5)
				self.press(Button.A, wait=1.5)
				self.press(Button.A, wait=1.5)  # 2000W
				if not self.checkIfAlive(): return

			self.wait(2.0)
			self.press(Button.A, wait=3)
			self.press(Button.B, wait=1)
			self.press(Button.B, wait=1)
			self.press(Button.B, wait=1)
			while not self.isContainTemplate('Network_Offline.png', 0.8):
				self.wait(0.5)
			self.timeLeap()
			self.wait(0.5)
			self.press(Button.Y)  # YY-COMMUNICATION
			while not self.isContainTemplate('internet.png', 0.8):
				self.wait(0.5)
			self.press(Button.PLUS, wait=10)  # Internet
			while not self.isContainTemplate('dialogue.png', 0.8):
				self.wait(0.5)
			self.press(Button.B, wait=1)
			self.press(Button.B)  # back to wild-area
			while not self.isContainTemplate('Network_Online.png', 0.8): # online check
				self.wait(0.5)
			self.wait(0.5)
			self.press(Button.A, wait=5)  # open raid
			self.press(Button.A, wait=1)  # open raid
			while not self.isContainTemplate('change_pokemon.png', 0.8): # timing check
				self.wait(0.5)
			self.press(Direction.UP, wait=0.5)  # 準備完了
			self.press(Button.A, wait=0.5)  # 準備完了
			if self.isContainTemplate('start_battle.png'):
				t = 0
				while t < 160:  # wait for 160 sec
					t += 1
					if self.isContainTemplate('4check.png', 0.85):
						self.press(Button.A)  # start if there are 4 people checked
					elif self.isContainTemplate('fight.png'):  # In case Starting manually
						break
					else:
						self.wait(1.0)
			if not self.isContainTemplate("lonely.png", 0.9):
				for i in range(10):
					self.press(Button.A, wait=0.8)
				while not self.isContainTemplate('catch_or_not.png'):  # To quit game
					if self.isContainTemplate('fight.png') or self.isContainTemplate('cheers.png'):  # press A
						for i in range(8):
							self.press(Button.A, wait=0.5)
				j += 1
			self.press(Button.HOME, wait=2)  # EXIT Game
			self.press(Button.X, wait=0.6)
			self.press(Button.A, wait=2.5)  # closed
			self.press(Button.A, wait=2.0)  # Choose game
			self.press(Button.A)  # User selection
			while not self.isContainTemplate('OP.png', 0.7): # recognize Opening
				self.wait(1)
			self.press(Button.A, wait=7.0)  # load save-data
			print('{} s 経過'.format(time.time() - s))
# if not self.checkIfAlive(): return


# タワー周回(移植)
class Tower_loop(PythonCommand):  # 受付からスタート
	def __init__(self, name):
		super(Tower_loop, self).__init__(name)

	def do(self):
		while self.checkIfAlive():
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=17)
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=1)
			self.press(Direction.UP, wait=1)

			self.press(Button.A, wait=1)
			self.press(Button.A, wait=1)
			self.press(Direction.UP, wait=1)
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=1)

			self.press(Button.A, wait=17)
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=1)
			self.press(Button.B, wait=1)
			self.press(Button.B, wait=1)

			self.press(Direction.UP, wait=1)


# タワー周回(画像認識)
class Tower_loop2(ImageProcPythonCommand):  # 受付からスタート
	def __init__(self, name, cam):
		super(Tower_loop2, self).__init__(name, cam)

	def do(self):
		# dirpath = 'C:/Users/u250389i/Documents/GitHub/Poke-Controller_edit/SerialController/Template/Tower/'
		while self.checkIfAlive():
			self.wait(0.5)
			if self.isContainTemplate('Tower/Fainted.png', 0.9):
				self.wait(1.5)
				print('瀕死')
				self.press(Direction.DOWN, wait=1)
				self.wait(1.5)
				if self.isContainTemplate('Tower/Fainted.png', 0.9):  # 瀕死が2体居たとき用
					self.press(Direction.DOWN, wait=1)
				self.press(Button.A, wait=0.5)
				self.press(Button.A, wait=0.5)
				self.press(Button.A, wait=1)
			elif self.isContainTemplate('Tower/choose.png', 0.7):
				self.wait(1.5)
				print('ポケモン選択')
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Direction.DOWN, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Direction.DOWN, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
			elif self.isContainTemplate('Tower/back.png', 0.8) and self.isContainTemplate('Tower/poke-status.png', 0.8):
				self.press(Button.B, wait=2)
				self.press(Button.B, wait=2)
			else:
				self.press(Button.A, wait=0.5)


class InfinityFeather(RankGlitchPythonCommand):
	def __init__(self, name):
		super(InfinityFeather, self).__init__(name)

	def do(self):
		# 時間確認用。使用時は "import time" すること
		# start = time.time()
		i = 0
		print('Start collecting feathers')
		while self.checkIfAlive():
			self.wait(0.7)
			i += 1
			print('Map')
			self.press(Button.X, wait=1.5)
			self.press(Button.A, wait=3.0)
			self.press(Direction(Stick.LEFT, 45), duration=0.05)
			self.press(Button.A, wait=1)
			self.press(Button.A, wait=4.0)
			print('pick feather')
			self.press([Direction.RIGHT, Direction.DOWN], duration=0.15)
			self.press(Direction.RIGHT, duration=3)
			self.press(Button.A, wait=0.3)
			self.press(Button.A, wait=0.3)
			self.press(Button.A, wait=0.3)
			self.press(Button.A, wait=0.3)
			print('Time leap')
			self.timeLeap()
		# tm = round(time.time() - start, 2)
		# print('Loop : {} in {} sec. Average: {} sec/loop'.format(i, tm, round(tm / i, 2)))


class Fossil_shiny(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(Fossil_shiny, self).__init__(name, cam)

	'''
	head = {0 : "カセキのトリ", 1 : "カセキのサカナ"}
	body = {0 : "カセキのリュウ", 1 : "カセキのクビナガ"}
	'''

	def fossil_loop(self, head=0, body=0):
		start = time.time()
		i = 0
		while True:
			for j in range(30):
				print(str(30 * i + j + 1) + "体目 ({}/30 of a box)".format(j + 1))
				self.press(Button.A, wait=0.75)
				self.press(Button.A, wait=0.75)

				if head == 1:
					self.press(Direction.DOWN, duration=0.07, wait=0.75)  # select fossil
				self.press(Button.A, wait=0.75)  # determine fossil

				if body == 1:
					self.press(Direction.DOWN, duration=0.07, wait=0.75)  # select fossil
				self.press(Button.A, wait=0.75)  # determine fossil

				self.press(Button.A, wait=0.75)  # select "それでよければ"
				while not self.isContainTemplate('Network_Offline.png', 0.8):
					self.press(Button.B, wait=0.5)
				self.wait(1.0)

			# open up pokemon box
			self.press(Button.X, wait=1)
			self.press(Direction.RIGHT, duration=0.07, wait=1)
			self.press(Button.A, wait=2)
			self.press(Button.R, wait=2)

			is_contain_shiny = self.CheckBox()
			# tm = round(time.time() - start, 2)
			# print('Loop : {} in {} sec. Average: {} sec/loop'.format(i, tm, round(tm / i, 2)))
			if is_contain_shiny:
				print('Shiny!')
				break

			self.press(Button.HOME, wait=2)  # EXIT Game
			self.press(Button.X, wait=0.6)
			self.press(Button.A, wait=2.5)  # closed
			self.press(Button.A, wait=2.0)  # Choose game
			self.press(Button.A)  # User selection
			while not self.isContainTemplate('OP.png', 0.7):  # recognize Opening
				self.wait(0.2)
			self.press(Button.A)  # load save-data
			while not self.isContainTemplate('Network_Offline.png', 0.8):
				self.wait(0.5)
			self.wait(1.0)
			i += 1

	def CheckBox(self):
		row = 5
		col = 6
		for i in range(0, row):
			for j in range(0, col):
				# if shiny, then stop
				if self.isContainTemplate('shiny_mark.png', threshold=0.9):
					return True
				# Maybe this threshold works for only Japanese version.
				if self.isContainTemplate('status.png', threshold=0.7):
					pass
				if not j == col - 1:
					if i % 2 == 0:
						self.press(Direction.RIGHT, wait=0.2)
					else:
						self.press(Direction.LEFT, wait=0.2)
			self.press(Direction.DOWN, wait=0.2)
		return False


class Fossil_shiny_00(Fossil_shiny):  # パッチラゴン
	def __init__(self, name, cam):
		super(Fossil_shiny, self).__init__(name, cam)

	def do(self):
		self.fossil_loop(0, 0)


class Fossil_shiny_01(Fossil_shiny):  # パッチルドン
	def __init__(self, name, cam):
		super(Fossil_shiny, self).__init__(name, cam)

	def do(self):
		self.fossil_loop(0, 1)


class Fossil_shiny_10(Fossil_shiny):  # ウオノラゴン
	def __init__(self, name, cam):
		super(Fossil_shiny, self).__init__(name, cam)

	def do(self):
		self.fossil_loop(1, 0)


class Fossil_shiny_11(Fossil_shiny):  # ウオチルドン
	def __init__(self, name, cam):
		super(Fossil_shiny, self).__init__(name, cam)

	def do(self):
		self.fossil_loop(1, 1)

class AutoRaid(ImageProcPythonCommand):
	def __init__(self, name, cam):
		super(AutoRaid, self).__init__(name, cam)

	def do(self):
		loop = 1
		while True:
			print(f"loop : {loop}")
			self.wait(1.0)
			print("Go Solo Raid battle.")
			while not self.isContainTemplate("raid_menu.png", 0.9):
				self.press(Button.A, wait=1.5)
			self.press(Direction.DOWN, duration=0.07, wait=1.0)
			self.press(Button.A, wait=1.5)
			self.press(Button.A, wait=1.5)
			print("Raid battle start.")
			while not self.isContainTemplate("catch_or_not.png", 0.7):
				if self.isContainTemplate('fight.png') or self.isContainTemplate("cheers.png", 0.8):  # press A
					for i in range(8):
						self.press(Button.A, wait=0.5)
				if self.isContainTemplate("Network_Offline.png", 0.8):
					break
			print("Raid Battle Finish")
			if self.isContainTemplate("catch_or_not.png", 0.7):
				self.press(Direction.DOWN, duration=0.07, wait=1.0)
			while not self.isContainTemplate("Network_Offline.png", 0.8):
				self.press(Button.A, wait=1.0)
			loop += 1
			# self.press(Direction.UP, duration=0.07, wait=1.0)

# マジカル交換
class Magical_Trade(PythonCommand):
	def __init__(self, name):
		super(Magical_Trade, self).__init__(name)
		self.maxpcnt = 30 # ポケモン交換したい数
		self.pcnt = 0 # ポケモンの数

	def do(self):
		while True:
			if self.pcnt < self.maxpcnt:
				self.pcnt += 1
			# 開始
				self.press(Button.Y, wait=1.5)
				self.press(Direction.DOWN, wait=1.0)
				self.press(Button.A, wait=3.0)
				# ポケモン選択
				self.pselect()
				self.wait(1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=6.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=90)

				# 交換相手検索中

				self.press(Button.Y, wait=60)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)
				self.press(Button.A, wait=1.0)

			else:
				self.wait(1.0)
				print('done')
				self.finish()


	def pselect(self):
		bcnt = (self.pcnt - 1) % 30 + 1
		x = (bcnt -1) % 6
		# y = (bcnt -1) / 6
		y = (bcnt -1) // 6 #整数除算

		# for i = 0, i < x, i += 1
		for i in range(0, x, 1):
			self.press(Direction.RIGHT, wait=0.5)

		# for i = 0, i < y, i += 1
		for i in range(0, y, 1):
			self.press(Direction.DOWN, wait=0.5)




class MyDialog(simpledialog.Dialog):
	def __init__(self, parent, title):
		super(MyDialog, self).__init__(parent, title)

	def body(self, master):
		self.geometry("200x75")
		tk.Label(master, text="Input Value").grid(row=0)
		self.e1 = tk.Entry(master)
		self.e1.grid(row=0, column=1)
		return self.e1  # initial focus

	def apply(self):
		first = self.e1.get()
		self.result = first

	def input_value(self, title=""):
		root1 = tk.Tk()
		root1.withdraw()
		value = MyDialog(root1, title)
		try:
			ret_value = int(value.result)
		except:
			print("数値を入力してください")
			ret_value = 0
		return ret_value



# sample initial code
# Copy and paste this class and write codes in start method.
# After you write the codes, don't forget to add commands dictionary below.
# このクラスをコピぺしてstartメソッドの続きにコードを書いてください
# コードを書き終わったら, 下のcommands変数に追加するのを忘れないように
class Sample(PythonCommand):
	def __init__(self, name):
		super(Sample, self).__init__(name)

	def do(self):
		self.wait(1)


# Add commands you want to use
# 使用したいコマンドをここに追加してください
commands = {
	'A連打': Mash_A,
	'自動リーグ周回': AutoLeague,
	'仮:自動孵化(画像認識)': AutoHatching,
	'固定数孵化(画像認識)': CountHatching,
	'自動リリース': AutoRelease,
	'無限ワット(ランクマ)': InfinityWatt,
	'無限IDくじ(ランクマ)': InfinityLottery,
	'無限きのみ(ランクマ)': InfinityBerry,
	'無限カフェ(ランクマ)': InfinityCafe,
	'自動リーグ周回(画像認識)': AutoLeagueIP,
	'無限羽回収(ランクマ)': InfinityFeather,
	'カセキ色厳選(パッチラゴン)': Fossil_shiny_00,
	'カセキ色厳選(パッチルドン)': Fossil_shiny_01,
	'カセキ色厳選(ウオノラゴン)': Fossil_shiny_10,
	'カセキ色厳選(ウオチルドン)': Fossil_shiny_11,
	'自動孵化': Hatch,
	'seed消費': Seedconsume,
	'Box逃がし': Release,
	'タワー周回': Tower_loop,
	'タワー周回(画像認識)': Tower_loop2,
	'シード消費後レイド探し(画像認識)': raid_search,
	'3日後レイド配布(画像認識)': three_day_raid_loop,
	'レイド配布(画像認識)': raid_loop,
	'レイド周回(画像認識)': AutoRaid,
	'マジカル交換': Magical_Trade

}

# Add commands as utility you want to use
# ユーティリティとして使用したいコマンドを追加してください
utils = {
	'コントローラ同期': Sync,
	'コントローラ同期解除': Unsync,
}
