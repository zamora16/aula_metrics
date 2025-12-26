#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para generar datos de demostración de AulaMetrics
Genera grupos académicos con alumnos y tutores
"""

# Configuración
GRUPOS = {
    'eso1': ['A', 'B', 'C'],
    'eso2': ['A', 'B', 'C'],
    'eso3': ['A', 'B'],
    'eso4': ['A', 'B'],
    'bach1': ['A'],
    'bach2': ['A'],
}

ALUMNOS_POR_GRUPO = 10

# Nombres para generar alumnos
NOMBRES = ['Juan', 'María', 'Pedro', 'Ana', 'Luis', 'Carmen', 'José', 'Laura', 'Carlos', 'Elena',
           'Miguel', 'Isabel', 'David', 'Sofía', 'Antonio', 'Lucía', 'Francisco', 'Paula', 'Manuel', 'Andrea']
APELLIDOS = ['García', 'López', 'Martínez', 'Rodríguez', 'Fernández', 'Sánchez', 'Gómez', 'Pérez', 
             'Ruiz', 'Díaz', 'Jiménez', 'Moreno', 'Álvarez', 'Romero', 'Torres', 'Navarro']

def get_course_name(course_level, section):
    """Convierte código de curso a nombre legible"""
    mapping = {
        'eso1': '1º ESO',
        'eso2': '2º ESO',
        'eso3': '3º ESO',
        'eso4': '4º ESO',
        'bach1': '1º Bachillerato',
        'bach2': '2º Bachillerato',
    }
    return f"{mapping[course_level]} {section}"

def generate_xml():
    xml = ['<?xml version="1.0" encoding="utf-8"?>']
    xml.append('<odoo>')
    xml.append('    <data noupdate="0">')
    xml.append('')
    xml.append('        <!-- ========================================== -->')
    xml.append('        <!-- DATOS DE DEMOSTRACIÓN GENERADOS AUTOMÁTICAMENTE -->')
    xml.append('        <!-- ========================================== -->')
    xml.append('')
    
    alumno_counter = 0
    tutor_counter = 0
    all_groups = []
    
    # Generar tutores y grupos
    for course_level, sections in GRUPOS.items():
        for section in sections:
            tutor_counter += 1
            group_id = f"group_{course_level}_{section.lower()}"
            tutor_id = f"user_tutor_{tutor_counter}"
            course_name = get_course_name(course_level, section)
            
            # Tutor
            tutor_name = f"{NOMBRES[tutor_counter % len(NOMBRES)]} {APELLIDOS[tutor_counter % len(APELLIDOS)]}"
            xml.append(f'        <!-- Tutor: {course_name} -->')
            xml.append(f'        <record id="{tutor_id}" model="res.users">')
            xml.append(f'            <field name="name">Prof. {tutor_name}</field>')
            xml.append(f'            <field name="login">tutor.{course_level}.{section.lower()}</field>')
            xml.append(f'            <field name="password">tutor123</field>')
            xml.append(f'            <field name="groups_id" eval="[(6, 0, [ref(\'base.group_user\'), ref(\'aula_metrics.group_aulametrics_tutor\')])]"/>')
            xml.append(f'        </record>')
            xml.append('')
            
            # Grupo académico (ANTES de los alumnos)
            xml.append(f'        <!-- Grupo Académico: {course_name} -->')
            xml.append(f'        <record id="{group_id}" model="aulametrics.academic_group">')
            xml.append(f'            <field name="name">{course_name}</field>')
            xml.append(f'            <field name="course_level">{course_level}</field>')
            xml.append(f'            <field name="tutor_id" ref="{tutor_id}"/>')
            xml.append(f'        </record>')
            xml.append('')
            
            # Alumnos del grupo (DESPUÉS del grupo)
            xml.append(f'        <!-- Alumnos: {course_name} -->')
            for i in range(ALUMNOS_POR_GRUPO):
                alumno_counter += 1
                alumno_id = f"partner_alumno_{alumno_counter}"
                
                nombre = NOMBRES[alumno_counter % len(NOMBRES)]
                apellido = APELLIDOS[alumno_counter % len(APELLIDOS)]
                apellido2 = APELLIDOS[(alumno_counter + 5) % len(APELLIDOS)]
                
                xml.append(f'        <record id="{alumno_id}" model="res.partner">')
                xml.append(f'            <field name="name">{nombre} {apellido} {apellido2}</field>')
                xml.append(f'            <field name="email">alumno{alumno_counter}@test.com</field>')
                xml.append(f'            <field name="academic_group_id" ref="{group_id}"/>')
                xml.append(f'        </record>')
            xml.append('')
            
            all_groups.append({
                'group_id': group_id,
                'course_name': course_name
            })
    
    xml.append('    </data>')
    xml.append('</odoo>')
    
    return '\n'.join(xml)

if __name__ == '__main__':
    xml_content = generate_xml()
    
    # Guardar archivo
    output_file = '/mnt/extra-addons/aula_metrics/data/demo/users_groups.xml'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(xml_content)
    
    print(f"✅ Archivo generado: {output_file}")
    print(f"📊 Estadísticas:")
    
    total_groups = sum(len(sections) for sections in GRUPOS.values())
    total_students = total_groups * ALUMNOS_POR_GRUPO
    
    print(f"   - Grupos: {total_groups}")
    print(f"   - Tutores: {total_groups}")
    print(f"   - Alumnos: {total_students}")
    print(f"   - Total usuarios: {total_groups + total_students}")
