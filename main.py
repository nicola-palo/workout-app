# Import necessary KivyMD and Kivy components
from kivymd.app import MDApp
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.textfield import MDTextField
from kivymd.uix.list import OneLineListItem, TwoLineListItem, MDList
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.selectioncontrol import MDCheckbox
from kivymd.uix.tab import MDTabs, MDTabsBase
from kivymd.uix.card import MDCard
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty, ObjectProperty, BooleanProperty, NumericProperty
from functools import partial
from kivy.utils import get_color_from_hex, platform
import sqlite3
import os

# Custom Tab class for MDTabs implementation
class Tab(MDBoxLayout, MDTabsBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"

# Custom list item for draggable functionality
class DraggableListItem(MDList):
    pass

# Main menu screen class
class MainMenu(Screen):
    pass

# Base screen class with common functionality
class BaseScreen(Screen):
    dialog = None
    confirm_dialog = None
    
    # Show confirmation dialog with custom title, text and callback
    def show_confirm_dialog(self, title, text, on_confirm):
        self.confirm_dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDRaisedButton(
                    text="ANNULLA",
                    on_release=lambda x: self.dismiss_confirm_dialog()
                ),
                MDRaisedButton(
                    text="CONFERMA",
                    on_release=lambda x: self._handle_confirm(on_confirm)
                ),
            ],
        )
        self.confirm_dialog.open()
    
    # Dismiss confirmation dialog
    def dismiss_confirm_dialog(self):
        if self.confirm_dialog:
            self.confirm_dialog.dismiss()
            self.confirm_dialog = None
    
    # Handle confirmation callback
    def _handle_confirm(self, callback):
        if self.confirm_dialog:
            self.confirm_dialog.dismiss()
            self.confirm_dialog = None
            callback()

    # Get database connection with error handling
    def get_db_connection(self):
        try:
            return sqlite3.connect(MDApp.get_running_app().get_database_path())
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

# Exercise Manager screen for handling muscle groups
class ExerciseManager(BaseScreen):
    def on_enter(self):
        self.load_muscle_groups()
    
    # Show delete confirmation for muscle group
    def show_delete_confirmation(self, group_id):
        self.show_confirm_dialog(
            "Conferma eliminazione",
            "Sei sicuro di voler eliminare questo gruppo muscolare?",
            lambda: self.delete_group(group_id)
        )
    
    # Load and display muscle groups
    def load_muscle_groups(self):
        self.ids.muscle_group_list.clear_widgets()
        conn = self.get_db_connection()
        if not conn:
            return
        
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM muscle_groups")
            groups = c.fetchall()
            
            for group in groups:
                # Create list item with delete button for each group
                item = OneLineListItem(text=group[1], text_color=(1, 1, 1, 1))
                layout = MDBoxLayout(
                    adaptive_height=True,
                    spacing="10dp",
                    padding=("10dp", "0dp", "10dp", "0dp")
                )
                
                delete_btn = MDIconButton(
                    icon="delete",
                    theme_text_color="Custom",
                    text_color=(1, 0, 0, 1),
                    on_release=lambda x, gid=group[0]: self.show_delete_confirmation(gid)
                )
                
                layout.add_widget(item)
                layout.add_widget(delete_btn)
                
                item.bind(on_release=lambda x, gid=group[0]: self.show_exercises(gid))
                self.ids.muscle_group_list.add_widget(layout)
        finally:
            conn.close()

    # Show dialog to add new muscle group
    def show_add_group_dialog(self):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Aggiungi Gruppo Muscolare",
                type="custom",
                content_cls=MDTextField(hint_text="Nome del gruppo muscolare"),
                buttons=[
                    MDRaisedButton(
                        text="ANNULLA",
                        on_release=lambda x: self.dialog.dismiss()
                    ),
                    MDRaisedButton(
                        text="AGGIUNGI",
                        on_release=lambda x: self.add_muscle_group()
                    ),
                ],
            )
        self.dialog.open()
    
    # Add new muscle group to database
    def add_muscle_group(self):
        if not self.dialog.content_cls.text:
            return
            
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("INSERT INTO muscle_groups (name) VALUES (?)",
                     (self.dialog.content_cls.text,))
            conn.commit()
        finally:
            conn.close()
            
        self.dialog.dismiss()
        self.dialog = None
        self.load_muscle_groups()
    
    # Delete muscle group and related exercises
    def delete_group(self, group_id):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            # Delete related exercises first
            c.execute("DELETE FROM exercises WHERE muscle_group_id = ?", (group_id,))
            # Then delete the group
            c.execute("DELETE FROM muscle_groups WHERE id = ?", (group_id,))
            conn.commit()
        finally:
            conn.close()
        self.load_muscle_groups()
    
    # Navigate to exercise list screen
    def show_exercises(self, group_id):
        screen = self.manager.get_screen('exercise_list')
        screen.current_group = group_id
        screen.load_exercises()
        self.manager.current = 'exercise_list'

# Exercise List screen for managing exercises within a muscle group
class ExerciseList(BaseScreen):
    current_group = NumericProperty(None)
    
    def on_enter(self):
        if self.current_group:
            self.load_exercises()
    
    # Load and display exercises for selected muscle group
    def load_exercises(self):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            # Get muscle group name
            c.execute("SELECT name FROM muscle_groups WHERE id = ?", (self.current_group,))
            group_name = c.fetchone()[0]
            self.ids.topbar.title = f"Esercizi - {group_name}"
            
            # Load exercises
            self.ids.exercise_list.clear_widgets()
            c.execute("SELECT id, name FROM exercises WHERE muscle_group_id = ?", (self.current_group,))
            exercises = c.fetchall()
            
            for exercise in exercises:
                self._add_exercise_item(exercise)
        finally:
            conn.close()
    
    # Add exercise item to the list with delete button
    def _add_exercise_item(self, exercise):
        item = OneLineListItem(text=exercise[1])
        layout = MDBoxLayout(
            adaptive_height=True,
            spacing="10dp",
            padding=("10dp", "0dp", "10dp", "0dp")
        )
        
        delete_btn = MDIconButton(
            icon="delete",
            theme_text_color="Custom",
            text_color=(1, 0, 0, 1),
            on_release=lambda x, eid=exercise[0]: self.show_delete_confirmation(eid)
        )
        
        layout.add_widget(item)
        layout.add_widget(delete_btn)
        self.ids.exercise_list.add_widget(layout)
    
    # Show delete confirmation for exercise
    def show_delete_confirmation(self, exercise_id):
        self.show_confirm_dialog(
            "Conferma eliminazione",
            "Sei sicuro di voler eliminare questo esercizio?",
            lambda: self.delete_exercise(exercise_id)
        )
    
    # Show dialog to add new exercise
    def show_add_exercise_dialog(self):
        if not self.dialog:
            self.dialog = MDDialog(
                title="Aggiungi Esercizio",
                type="custom",
                content_cls=MDTextField(hint_text="Nome dell'esercizio"),
                buttons=[
                    MDRaisedButton(
                        text="ANNULLA",
                        on_release=lambda x: self.dialog.dismiss()
                    ),
                    MDRaisedButton(
                        text="AGGIUNGI",
                        on_release=lambda x: self.add_exercise()
                    ),
                ],
            )
        self.dialog.open()
    
    # Add new exercise to database
    def add_exercise(self):
        if not self.dialog.content_cls.text:
            return
            
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("""
                INSERT INTO exercises (name, muscle_group_id)
                VALUES (?, ?)
            """, (self.dialog.content_cls.text, self.current_group))
            conn.commit()
        finally:
            conn.close()
            
        self.dialog.dismiss()
        self.dialog = None
        self.load_exercises()
    
    # Delete exercise from database
    def delete_exercise(self, exercise_id):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
            conn.commit()
        finally:
            conn.close()
        self.load_exercises()

# Workout Creator screen for managing workout routines
class WorkoutCreator(BaseScreen):
    def on_enter(self):
        self.load_workouts()
    
    # Load and display workout routines
    def load_workouts(self):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("SELECT id, name, timer FROM workouts")
            workouts = c.fetchall()
            
            self.ids.workout_list.clear_widgets()
            for workout in workouts:
                self._add_workout_item(workout)
        finally:
            conn.close()
    
    # Add workout item to the list with timer and delete button
    def _add_workout_item(self, workout):
        item = TwoLineListItem(
            text=workout[1],
            secondary_text=f"Timer: {workout[2]} min"
        )
        
        layout = MDBoxLayout(
            adaptive_height=True,
            spacing="10dp",
            padding=("10dp", "0dp", "10dp", "0dp")
        )
        
        delete_btn = MDIconButton(
            icon="delete",
            theme_text_color="Custom",
            text_color=(1, 0, 0, 1),
            on_release=lambda x, wid=workout[0]: self.show_delete_confirmation(wid)
        )
        
        item.bind(on_release=lambda x, wid=workout[0]: self.show_workout_detail(wid))
        layout.add_widget(item)
        layout.add_widget(delete_btn)
        self.ids.workout_list.add_widget(layout)

    # Show delete confirmation for workout
    def show_delete_confirmation(self, workout_id):
        self.show_confirm_dialog(
            "Conferma eliminazione",
            "Sei sicuro di voler eliminare questa scheda?",
            lambda: self.delete_workout(workout_id)
        )
    
    # Delete workout and related exercises
    def delete_workout(self, workout_id):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            # Delete workout exercises first
            c.execute("DELETE FROM workout_exercises WHERE workout_id = ?", (workout_id,))
            # Then delete the workout
            c.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
            conn.commit()
        finally:
            conn.close()
        self.load_workouts()
    
    # Show dialog to add new workout
    def show_add_workout_dialog(self):
        if not self.dialog:
            # Create input fields for workout name and timer
            content = MDBoxLayout(
                orientation='vertical',
                spacing="10dp",
                padding="10dp",
                size_hint_y=None,
                height="120dp"
            )
            
            content.add_widget(MDTextField(
                hint_text="Nome Scheda",
                mode="rectangle",
            ))
            
            content.add_widget(MDTextField(
                hint_text="Timer (minuti)",
                mode="rectangle",
                input_filter="int"
            ))
            
            self.dialog = MDDialog(
                title="Nuova Scheda",
                type="custom",
                content_cls=content,
                buttons=[
                    MDRaisedButton(
                        text="ANNULLA",
                        on_release=lambda x: self.dialog.dismiss()
                    ),
                    MDRaisedButton(
                        text="CREA",
                        on_release=lambda x: self.add_workout()
                    ),
                ],
            )
        self.dialog.open()

    # Add new workout to database
    def add_workout(self):
        content = self.dialog.content_cls
        name = content.children[1].text
        timer = content.children[0].text
        
        if not name or not timer:
            return
            
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            # Insert new workout
            c.execute("INSERT INTO workouts (name, timer) VALUES (?, ?)",
                     (name, int(timer)))
            workout_id = c.lastrowid
            conn.commit()
            
            self.dialog.dismiss()
            self.dialog = None
            self.show_workout_detail(workout_id)
        finally:
            conn.close()
    
    # Navigate to workout detail screen
    def show_workout_detail(self, workout_id):
        screen = self.manager.get_screen('workout_detail')
        screen.workout_id = workout_id
        screen.load_workout()
        self.manager.current = 'workout_detail'

# Workout Detail screen for managing exercises within a workout
class WorkoutDetail(BaseScreen):
    workout_id = NumericProperty(None)
    selected_group = NumericProperty(None)
    
    # Load workout details and exercises
    def load_workout(self):
        if not self.workout_id:
            return
            
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            # Get workout name
            c.execute("SELECT name FROM workouts WHERE id = ?", (self.workout_id,))
            workout_name = c.fetchone()[0]
            self.ids.detail_topbar.title = f"Modifica - {workout_name}"
        finally:
            conn.close()
            
        self.load_groups()
        self.load_preview()

    # Load and display muscle groups
    def load_groups(self):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("SELECT id, name FROM muscle_groups")
            groups = c.fetchall()
            
            self.ids.group_list.clear_widgets()
            for group in groups:
                item = OneLineListItem(text=group[1])
                item.bind(on_release=lambda x, gid=group[0]: self.select_group(gid))
                self.ids.group_list.add_widget(item)
        finally:
            conn.close()
    
    # Select muscle group and load its exercises
    def select_group(self, group_id):
        self.selected_group = group_id
        self.load_exercises(group_id)
        self.ids.tabs.switch_tab("Esercizi")
    
    # Load exercises for selected muscle group
    def load_exercises(self, group_id):
        self.selected_group = group_id
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("SELECT id, name FROM exercises WHERE muscle_group_id = ?", (group_id,))
            exercises = c.fetchall()
            
            self.ids.exercise_list.clear_widgets()
            for exercise in exercises:
                self._add_exercise_item(exercise)
        finally:
            conn.close()

    # Add exercise item to list with add button
    def _add_exercise_item(self, exercise):
        ex_layout = MDBoxLayout(
            orientation='horizontal',
            adaptive_height=True,
            spacing="10dp",
            padding=["10dp", "5dp", "10dp", "5dp"]
        )
        
        item = OneLineListItem(text=exercise[1])
        add_btn = MDIconButton(
            icon="plus",
            on_release=lambda x, eid=exercise[0], name=exercise[1]: self.show_add_exercise_dialog(eid, name)
        )
        
        ex_layout.add_widget(item)
        ex_layout.add_widget(add_btn)
        self.ids.exercise_list.add_widget(ex_layout)
    
    # Show dialog to add exercise to workout
    def show_add_exercise_dialog(self, exercise_id, exercise_name):
        if not self.dialog:
            content = MDBoxLayout(
                orientation='vertical',
                spacing="10dp",
                padding="10dp",
                size_hint_y=None,
                height="120dp"
            )
            
            # Fields for sets and reps
            content.add_widget(MDTextField(
                hint_text="Serie",
                mode="rectangle",
                input_filter="int"
            ))
            
            content.add_widget(MDTextField(
                hint_text="Ripetizioni",
                mode="rectangle",
                input_filter="int"
            ))
            
            self.dialog = MDDialog(
                title=f"Aggiungi {exercise_name}",
                type="custom",
                content_cls=content,
                buttons=[
                    MDRaisedButton(
                        text="ANNULLA",
                        on_release=lambda x: self.dialog.dismiss()
                    ),
                    MDRaisedButton(
                        text="AGGIUNGI",
                        on_release=lambda x, eid=exercise_id: self.add_exercise_to_workout(eid)
                    ),
                ],
            )
        self.dialog.open()
    
    # Add exercise to workout with sets and reps
    def add_exercise_to_workout(self, exercise_id):
        content = self.dialog.content_cls
        sets = content.children[1].text
        reps = content.children[0].text
        
        if not sets or not reps:
            return
            
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("""
                INSERT INTO workout_exercises (workout_id, exercise_id, sets, reps)
                VALUES (?, ?, ?, ?)
            """, (self.workout_id, exercise_id, int(sets), int(reps)))
            conn.commit()
        finally:
            conn.close()
            
        self.dialog.dismiss()
        self.dialog = None
        self.load_preview()

    # Load workout preview with exercises grouped by muscle group
    def load_preview(self):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            # Get exercises with muscle group info
            c.execute("""
                SELECT mg.name as group_name, e.name as ex_name, we.sets, we.reps, we.id
                FROM workout_exercises we
                JOIN exercises e ON we.exercise_id = e.id
                JOIN muscle_groups mg ON e.muscle_group_id = mg.id
                WHERE we.workout_id = ?
                ORDER BY mg.name
            """, (self.workout_id,))
            exercises = c.fetchall()
            
            self.ids.preview_list.clear_widgets()
            current_group = None
            for group_name, ex_name, sets, reps, exercise_id in exercises:
                if group_name != current_group:
                    current_group = group_name
                    self._add_group_header(group_name)
                self._add_exercise_preview(ex_name, sets, reps, exercise_id)
        finally:
            conn.close()
    
    # Add muscle group header to preview
    def _add_group_header(self, group_name):
        self.ids.preview_list.add_widget(
            MDLabel(
                text=group_name,
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                bold=True,
                size_hint_y=None,
                height="40dp"
            )
        )
    
    # Add exercise item to preview with delete button
    def _add_exercise_preview(self, ex_name, sets, reps, exercise_id):
        exercise_layout = MDBoxLayout(
            orientation='horizontal',
            adaptive_height=True,
            spacing="10dp"
        )

        exercise_layout.add_widget(
            OneLineListItem(text=f"{ex_name}: {sets}x{reps}")
        )

        delete_btn = MDIconButton(
            icon="delete",
            theme_text_color="Custom",
            text_color=(1, 0, 0, 1),
            on_release=lambda x, eid=exercise_id: self.show_delete_confirmation(eid)
        )
        exercise_layout.add_widget(delete_btn)
        
        self.ids.preview_list.add_widget(exercise_layout)
    
    # Show delete confirmation for exercise in workout
    def show_delete_confirmation(self, exercise_id):
        self.show_confirm_dialog(
            "Conferma eliminazione",
            "Sei sicuro di voler eliminare questo esercizio dalla scheda?",
            lambda: self.delete_exercise(exercise_id)
        )
    
    # Delete exercise from workout
    def delete_exercise(self, exercise_id):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            c.execute("DELETE FROM workout_exercises WHERE id = ?", (exercise_id,))
            conn.commit()
        finally:
            conn.close()
        self.load_preview()

# Workout Executor screen for running workouts
class WorkoutExecutor(BaseScreen):
    timer_active = BooleanProperty(False)
    current_time = NumericProperty(0)
    selected_workout = ObjectProperty(None)
    background_mode = BooleanProperty(False)
    
    def on_enter(self):
        self._update_view_state(True)
        self.load_workouts()
        Clock.schedule_interval(self.update_timer, 1)

    def on_leave(self):
        if not self.background_mode:
            Clock.unschedule(self.update_timer)

    # Update view state between selection and execution screens
    def _update_view_state(self, show_selection):
        self.ids.workout_screen_manager.current = 'selection' if show_selection else 'execution'
    
    # Load available workouts
    def load_workouts(self):
        conn = self.get_db_connection()
        if not conn: 
            return
            
        try:
            c = conn.cursor()
            c.execute("SELECT id, name, timer FROM workouts")
            workouts = c.fetchall()
            
            self.ids.execution_list.clear_widgets()
            for workout in workouts:
                self.ids.execution_list.add_widget(
                    MDBoxLayout(size_hint_y=None, height="10dp")
                )
                self._add_workout_card(workout)
        finally:
            conn.close()
    
    # Add workout card with timer info
    def _add_workout_card(self, workout):
        card = MDCard(
            size_hint=(0.9, None),
            height="80dp",
            md_bg_color=get_color_from_hex("#283593"),
            radius=[8],
            pos_hint={"center_x": 0.5},
            elevation=0,
            ripple_behavior=True,
            on_release=lambda x: self.select_workout(workout)
        )
        
        box = MDBoxLayout(
            orientation='vertical',
            padding=["20dp", "10dp"]
        )
        
        box.add_widget(MDLabel(
            text=workout[1],
            halign="center",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            bold=True
        ))
        
        box.add_widget(MDLabel(
            text=f"Timer: {workout[2]} min",
            halign="center",
            theme_text_color="Custom",
            text_color=(0.8, 0.8, 0.8, 1),
            font_style="Caption"
        ))
        
        card.add_widget(box)
        self.ids.execution_list.add_widget(card)
    
    # Select workout and initialize timer
    def select_workout(self, workout):
        self.selected_workout = workout
        self.current_time = workout[2] * 60
        self.update_timer_display()
        self.load_workout_exercises(workout[0])
        self._update_view_state(False)
    
    # Load exercises for selected workout
    def load_workout_exercises(self, workout_id):
        conn = self.get_db_connection()
        if not conn: 
            return
            
        try:
            c = conn.cursor()
            # Get exercises with weight information
            c.execute("""
                SELECT mg.name, e.name, we.sets, we.reps, we.id, e.id, 
                    COALESCE((SELECT weight FROM exercise_weights WHERE exercise_id = e.id), 0) as weight
                FROM workout_exercises we
                JOIN exercises e ON we.exercise_id = e.id
                JOIN muscle_groups mg ON e.muscle_group_id = mg.id
                WHERE we.workout_id = ?
                ORDER BY mg.name
            """, (workout_id,))
            exercises = c.fetchall()
            
            self.ids.exercise_execution_list.clear_widgets()
            current_group = None
            exercise_count = 1
            
            for group, exercise, sets, reps, we_id, ex_id, weight in exercises:
                if group != current_group:
                    current_group = group
                    self._add_group_label(group)
                self._add_exercise_box(exercise_count, exercise, sets, reps, we_id, ex_id, weight)
                exercise_count += 1
        finally:
            conn.close()

    # Add group label to exercise list
    def _add_group_label(self, group):
        self.ids.exercise_execution_list.add_widget(
            MDLabel(
                text=group,
                theme_text_color="Custom",
                text_color=(1, 1, 1, 1),
                bold=True,
                size_hint_y=None,
                height="50dp",
                padding=["20dp", "10dp"]
            )
        )
    
    # Add exercise box with weight tracking
    def _add_exercise_box(self, number, exercise, sets, reps, we_id, ex_id, weight):
        card = MDCard(
            orientation='horizontal',
            size_hint_y=None,
            height="70dp",
            md_bg_color=get_color_from_hex("#283593"),
            radius=[8],
            padding=["16dp", "8dp"],
            spacing="8dp",
            elevation=0
        )
        
        # Exercise info layout
        info_box = MDBoxLayout(
            orientation='vertical',
            size_hint_x=0.6,
            spacing="4dp"
        )
        
        info_box.add_widget(MDLabel(
            text=f"{exercise}",
            theme_text_color="Custom",
            text_color=(1, 1, 1, 1),
            font_style="H6",
            bold=True
        ))
        
        info_box.add_widget(MDLabel(
            text=f"{sets}x{reps}",
            theme_text_color="Custom",
            text_color=(0.9, 0.9, 0.9, 1),
            font_style="Body1"
        ))
        
        card.add_widget(info_box)
        
        # Weight tracking layout
        weight_layout = MDBoxLayout(
            orientation='horizontal',
            size_hint_x=0.4,
            spacing="4dp"
        )
        
        saved_weight_label = MDLabel(
            text=f"[{str(weight)}kg]" if weight > 0 else "",
            theme_text_color="Custom",
            text_color=(0.9, 0.9, 0.9, 1),
            size_hint_x=0.4
        )
        weight_layout.add_widget(saved_weight_label)

        # Weight input field with auto-save
        def on_text(instance, value):
            try:
                if value:
                    weight = float(value)
                    saved_weight_label.text = f"[{weight}kg]"
                    self.save_weight(ex_id, value)
                else:
                    saved_weight_label.text = ""
            except ValueError:
                pass

        weight_field = MDTextField(
            text="",
            hint_text="kg",
            size_hint_x=0.6,
            input_filter="float",
            text_color_normal=(1, 1, 1, 1),
            text_color_focus=(1, 1, 1, 1),
            mode="line",
            line_color_focus=(1, 1, 1, 1)
        )
        weight_field.bind(text=on_text)
        weight_layout.add_widget(weight_field)
        
        card.add_widget(weight_layout)
        self.ids.exercise_execution_list.add_widget(card)
    
    # Save weight for exercise
    def save_weight(self, exercise_id, weight_text):
        if not weight_text: 
            return
            
        try:
            weight = float(weight_text)
            conn = self.get_db_connection()
            if not conn:
                return
                
            try:
                c = conn.cursor()
                # Check if weight record exists
                c.execute("SELECT id FROM exercise_weights WHERE exercise_id = ?", (exercise_id,))
                exists = c.fetchone()
                
                if exists:
                    c.execute("""UPDATE exercise_weights 
                               SET weight = ?, last_updated = CURRENT_TIMESTAMP 
                               WHERE exercise_id = ?""", (weight, exercise_id))
                else:
                    c.execute("""INSERT INTO exercise_weights (exercise_id, weight)
                               VALUES (?, ?)""", (exercise_id, weight))
                conn.commit()
            finally:
                conn.close()
        except ValueError:
            return
    
    # Update timer every second
    def update_timer(self, dt):
        if self.timer_active and self.current_time > 0:
            self.current_time -= 1
            self.update_timer_display()
            if self.current_time == 0:
                self.timer_active = False
    
    # Update timer display
    def update_timer_display(self):
        minutes = self.current_time // 60
        seconds = self.current_time % 60
        self.ids.timer_label.text = f"{minutes:02d}:{seconds:02d}"
    
    # Toggle timer start/stop
    def toggle_timer(self):
        if not self.selected_workout:
            return
        self.timer_active = not self.timer_active
    
    # Reset timer to initial value
    def reset_workout_timer(self):
        if not self.selected_workout:
            return
        self.current_time = self.selected_workout[2] * 60
        self.update_timer_display()
        self.timer_active = False

# Main application class
class WorkoutApp(MDApp):
    # Get platform-specific database path
    def get_database_path(self):
        if platform == 'android':
            from android.storage import app_storage_path
            return os.path.join(app_storage_path(), 'workout.db')
        return 'workout.db'

    # Get database connection
    def get_db_connection(self):
        try:
            return sqlite3.connect(self.get_database_path())
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

    # Build application
    def build(self):
        # Set theme colors
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.primary_hue = "900"
        self.theme_cls.accent_palette = "DeepOrange"
        self.theme_cls.theme_style = "Dark"
        
        self.create_database()
        
        # Create screen manager and add screens
        sm = ScreenManager()
        
        sm.add_widget(MainMenu(name='menu'))
        sm.add_widget(ExerciseManager(name='exercises'))
        sm.add_widget(ExerciseList(name='exercise_list'))
        sm.add_widget(WorkoutCreator(name='creator'))
        sm.add_widget(WorkoutDetail(name='workout_detail'))
        sm.add_widget(WorkoutExecutor(name='executor'))
        
        Builder.load_file('workout.kv')
        return sm

    # Create database tables
    def create_database(self):
        conn = self.get_db_connection()
        if not conn:
            return
            
        try:
            c = conn.cursor()
            
            # Create muscle groups table
            c.execute('''CREATE TABLE IF NOT EXISTS muscle_groups
                        (id INTEGER PRIMARY KEY, name TEXT UNIQUE)''')
            
            # Create exercises table
            c.execute('''CREATE TABLE IF NOT EXISTS exercises
                        (id INTEGER PRIMARY KEY,
                        name TEXT,
                        muscle_group_id INTEGER,
                        FOREIGN KEY (muscle_group_id) REFERENCES muscle_groups (id))''')
            
            # Create workouts table
            c.execute('''CREATE TABLE IF NOT EXISTS workouts
                        (id INTEGER PRIMARY KEY,
                        name TEXT,
                        timer INTEGER)''')
            
            # Create workout exercises table
            c.execute('''CREATE TABLE IF NOT EXISTS workout_exercises
                        (id INTEGER PRIMARY KEY,
                        workout_id INTEGER,
                        exercise_id INTEGER,
                        sets INTEGER,
                        reps INTEGER,
                        FOREIGN KEY (workout_id) REFERENCES workouts (id),
                        FOREIGN KEY (exercise_id) REFERENCES exercises (id))''')
            
            # Create exercise weights table
            c.execute('''CREATE TABLE IF NOT EXISTS exercise_weights
                        (id INTEGER PRIMARY KEY,
                        exercise_id INTEGER UNIQUE,
                        weight REAL,
                        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (exercise_id) REFERENCES exercises (id))''')
            
            conn.commit()
        finally:
            conn.close()

if __name__ == '__main__':
    WorkoutApp().run()