// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#ifdef QT_QUICK_LIB
#include "SaveCopies.h"
#include <QQuickImageProvider>
namespace library {
class SaveCopyPictureProvider final:public QQuickImageProvider {
public:
    explicit SaveCopyPictureProvider(const QSharedPointer<SaveCopyPictureData>& data):QQuickImageProvider(Image),m_data(data){}
    QImage requestImage(const QString& id,QSize* size,const QSize& requested) override;
private:
    QSharedPointer<SaveCopyPictureData> m_data;
};
}
#endif
