project('heos-controller',
         version: '0.1.0',
  meson_version: '>= 0.59.0',
        license: 'GPL-3.0-or-later'
)

python = import('python')
py_installation = python.find_installation('python3')

# Dependencies
dependency('glib-2.0')
dependency('gtk4')
dependency('libadwaita-1')

# Install Python files
py_installation.install_sources([
  'heos_controller_gtk.py',
  'heos_mdns.py',
  'device_cache.py',
],
  pure: true,
  subdir: 'heos_controller'
)

# Install UI files
install_data('window.ui',
  install_dir: get_option('datadir') / 'heos_controller'
)

# Create and install desktop file
desktop_file = configure_file(
  input: 'com.github.heoscontroller.desktop.in',
  output: 'com.github.heoscontroller.desktop',
  configuration: {
    'bindir': get_option('prefix') / get_option('bindir'),
  }
)

install_data(desktop_file,
  install_dir: get_option('datadir') / 'applications'
)

# Create launcher script
configure_file(
  input: 'heos-controller.in',
  output: 'heos-controller',
  configuration: {
    'PYTHON': py_installation.path(),
    'prefix': get_option('prefix'),
  },
  install_dir: get_option('bindir')
)
