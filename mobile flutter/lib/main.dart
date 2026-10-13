import 'package:flutter/material.dart';
import 'app.dart';
import 'core/constants/api_constants.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Load saved custom tunnel/server URL if configured by user
  await ApiConstants.initCustomBaseUrl();
  runApp(const GeiserApp());
}
