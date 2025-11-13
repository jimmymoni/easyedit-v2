import React, { useState } from 'react';
import { ContentAnalysis, Feature } from '../../types';
import * as api from '../../services/api';

interface KnowledgeBaseEditorProps {
  jobId: string;
  contentAnalysis: ContentAnalysis;
  onUpdate: (updated: ContentAnalysis) => void;
}

const KnowledgeBaseEditor: React.FC<KnowledgeBaseEditorProps> = ({
  jobId,
  contentAnalysis,
  onUpdate
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedKB, setEditedKB] = useState<ContentAnalysis>(contentAnalysis);
  const [isSaving, setIsSaving] = useState(false);

  const handleEditFeature = (featureId: string, updates: Partial<Feature>) => {
    const updatedFeatures = editedKB.features_discussed.map(f =>
      f.id === featureId ? { ...f, ...updates, user_edited: true } : f
    );

    // Recalculate duration if start/end changed
    const updatedFeaturesWithDuration = updatedFeatures.map(f => {
      if (f.id === featureId && (updates.start_time !== undefined || updates.end_time !== undefined)) {
        return { ...f, duration: f.end_time - f.start_time };
      }
      return f;
    });

    setEditedKB({
      ...editedKB,
      features_discussed: updatedFeaturesWithDuration
    });
  };

  const handleDeleteFeature = (featureId: string) => {
    const updatedFeatures = editedKB.features_discussed.filter(f => f.id !== featureId);
    setEditedKB({
      ...editedKB,
      features_discussed: updatedFeatures
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const response = await api.updateKnowledgeBase(jobId, editedKB);
      onUpdate(response.content_analysis);
      setIsEditing(false);
    } catch (error) {
      console.error('Failed to save knowledge base:', error);
      alert('Failed to save changes. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedKB(contentAnalysis);
    setIsEditing(false);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  if (!contentAnalysis || !contentAnalysis.features_discussed) {
    return null;
  }

  return (
    <div className="bg-[#181818] border border-[#2A2A2A] rounded-xl p-6 mb-4">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-[#FF6B35] font-semibold flex items-center">
          =Ú Content Knowledge Base
          {contentAnalysis.metadata?.user_modified && (
            <span className="ml-2 text-xs bg-[#FF6B35]/20 text-[#FF6B35] px-2 py-1 rounded">
              User Modified
            </span>
          )}
        </h3>

        {!isEditing && (
          <button
            onClick={() => setIsEditing(true)}
            className="text-sm text-[#EAEAEA] hover:text-[#FF6B35] transition-colors"
          >
             Edit
          </button>
        )}
      </div>

      {/* Main Topic */}
      <div className="mb-4">
        <label className="text-[#EAEAEA]/70 text-sm">Main Topic:</label>
        {isEditing ? (
          <input
            type="text"
            value={editedKB.main_topic}
            onChange={(e) => setEditedKB({ ...editedKB, main_topic: e.target.value })}
            className="w-full bg-[#0A0A0A] border border-[#2A2A2A] rounded px-3 py-2 text-[#EAEAEA] mt-1"
          />
        ) : (
          <p className="text-[#EAEAEA] font-medium mt-1">{editedKB.main_topic}</p>
        )}
      </div>

      {/* Features List */}
      <div>
        <label className="text-[#EAEAEA]/70 text-sm mb-2 block">
          Features Discussed: ({editedKB.features_discussed.length})
        </label>

        <div className="space-y-3">
          {editedKB.features_discussed.map((feature) => (
            <div key={feature.id} className="bg-[#0A0A0A] border border-[#2A2A2A] rounded-lg p-4">
              {isEditing ? (
                <div className="space-y-3">
                  {/* Feature Name */}
                  <input
                    type="text"
                    value={feature.name}
                    onChange={(e) => handleEditFeature(feature.id, { name: e.target.value })}
                    className="w-full bg-[#181818] border border-[#2A2A2A] rounded px-3 py-2 text-[#EAEAEA] font-semibold"
                    placeholder="Feature name"
                  />

                  {/* Description */}
                  <textarea
                    value={feature.description}
                    onChange={(e) => handleEditFeature(feature.id, { description: e.target.value })}
                    className="w-full bg-[#181818] border border-[#2A2A2A] rounded px-3 py-2 text-[#EAEAEA] text-sm"
                    placeholder="Description"
                    rows={2}
                  />

                  {/* Timestamps */}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[#EAEAEA]/70 text-xs">Start Time (seconds)</label>
                      <input
                        type="number"
                        value={feature.start_time}
                        onChange={(e) => {
                          const start = parseFloat(e.target.value);
                          handleEditFeature(feature.id, { start_time: start });
                        }}
                        className="w-full bg-[#181818] border border-[#2A2A2A] rounded px-3 py-2 text-[#EAEAEA] mt-1"
                      />
                    </div>
                    <div>
                      <label className="text-[#EAEAEA]/70 text-xs">End Time (seconds)</label>
                      <input
                        type="number"
                        value={feature.end_time}
                        onChange={(e) => {
                          const end = parseFloat(e.target.value);
                          handleEditFeature(feature.id, { end_time: end });
                        }}
                        className="w-full bg-[#181818] border border-[#2A2A2A] rounded px-3 py-2 text-[#EAEAEA] mt-1"
                      />
                    </div>
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDeleteFeature(feature.id)}
                    className="text-sm text-red-400 hover:text-red-300 transition-colors"
                  >
                    =Ñ Delete Feature
                  </button>
                </div>
              ) : (
                <div>
                  <div className="flex justify-between items-start mb-2">
                    <h4 className="text-[#EAEAEA] font-semibold">{feature.name}</h4>
                    <span className="text-[#EAEAEA]/70 text-sm">
                      {formatTime(feature.start_time)} - {formatTime(feature.end_time)}
                      <span className="ml-2">({(feature.duration / 60).toFixed(1)}min)</span>
                    </span>
                  </div>
                  <p className="text-[#EAEAEA]/70 text-sm">{feature.description}</p>
                  {feature.user_edited && (
                    <span className="text-xs text-[#FF6B35] mt-2 inline-block">
                       User Edited
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Save/Cancel Buttons */}
      {isEditing && (
        <div className="mt-4 flex space-x-3">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="flex-1 bg-[#FF6B35] hover:bg-[#FF8555] text-white font-semibold py-2 rounded transition-colors disabled:opacity-50"
          >
            {isSaving ? 'Saving...' : '=¾ Save Changes'}
          </button>
          <button
            onClick={handleCancel}
            disabled={isSaving}
            className="px-4 bg-[#2A2A2A] hover:bg-[#3A3A3A] text-[#EAEAEA] rounded transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
};

export default KnowledgeBaseEditor;
