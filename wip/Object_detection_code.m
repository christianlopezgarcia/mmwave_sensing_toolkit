clear;
delete(instrfindall)

% Create mmWaveRadar object and specify its properties.
tiradar = mmWaveRadar("TI IWR6843AOPEVM");
tiradar.AzimuthLimits = [-60 60];
tiradar.DetectionCoordinates = "Sensor rectangular";

% Close all open figures
close all

% Create bird's-eye plot GUI
f = figure('NumberTitle', 'off', 'Name', 'Object Detections with Angles');
axBEP = axes(f);
axis(axBEP, 'equal');
grid(axBEP, 'on');
grid(axBEP, 'minor');
cla(axBEP);
xLimits = [0, tiradar.MaximumRange];
yLimits = [-tiradar.MaximumRange, tiradar.MaximumRange];

bep = birdsEyePlot('Parent', axBEP, 'XLim', xLimits, 'YLim', yLimits);

% Plot coverage area
azFOV = tiradar.AzimuthLimits(2) - tiradar.AzimuthLimits(1);
caPlotter = coverageAreaPlotter(bep, 'DisplayName', 'Coverage Area', 'FaceColor', 'b');
plotCoverageArea(caPlotter, tiradar.MountingLocation(1:2), tiradar.MaximumRange, tiradar.MountingAngles(1), azFOV);

% Create detection plotter
detPlotter = detectionPlotter(bep, 'DisplayName', 'Detections', 'Marker', 'o', ...
                              'MarkerFaceColor', 'b', 'MarkerSize', 4);

% Initialize handle array for angle text
angleTextHandles = [];

while ishandle(f)
    % Read detections
    [objDetsRct, timestamp, measurements, overrun] = tiradar();
    numDets = numel(objDetsRct);
    pos = zeros(3, numDets);
    vel = zeros(3, numDets);
    angles = zeros(1, numDets);

    % Delete previous angle texts
    for h = angleTextHandles
    if isgraphics(h)
        delete(h);
    end
end
    angleTextHandles = [];

    for i = 1:numDets
        meas = objDetsRct{i}.Measurement;
        pos(:, i) = meas(1:3);
        vel(:, i) = meas(4:6);

        % Calculate azimuth angle from x and y
        x = meas(1);
        y = meas(2);
        angles(i) = atan2d(y, x);  % Angle in degrees

        % Display angle as text near the detection point
        txtStr = sprintf('%.1f°', angles(i));
        hText = text(axBEP, x, y, txtStr, 'FontSize', 9, 'Color', 'r', ...
                     'HorizontalAlignment', 'left', 'VerticalAlignment', 'bottom');
        angleTextHandles(end+1) = hText;
    end

    % Update detections on bird's-eye plot
    plotDetection(detPlotter, pos', vel');
    drawnow limitrate;
end

clear tiradar